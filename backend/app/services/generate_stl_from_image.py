import numpy as np
import trimesh
from PIL import Image
import io
import os
import uuid
import requests
import cv2
import logging
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.validation import make_valid
from shapely.ops import unary_union

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sand-backend")

def generate_stl_from_image(image_source, settings):
    logger.info("--- Side-Specific Framing with Debug Logging ---")
    
    try:
        # 1. Image Loading
        if isinstance(image_source, str):
            if image_source.startswith('http'):
                response = requests.get(image_source, timeout=15)
                img_data = io.BytesIO(response.content)
            else:
                with open(image_source, 'rb') as f:
                    img_data = io.BytesIO(f.read())
        else:
            img_data = io.BytesIO(image_source)

        # 2. Extract Settings
        wall_h = float(settings.get('wallHeight', 3.0))
        base_h = float(settings.get('basePlateThickness', 0.4))
        target_wall_width_mm = float(settings.get('wallThickness', 1.0))
        scale_percent = float(settings.get('scalePercent', 100)) / 100.0
        include_base = settings.get('basePlate', True)
        pixel_to_mm = 0.1
        radius_px = (target_wall_width_mm / pixel_to_mm) / 2.0

        # 3. Pre-processing
        img_raw = Image.open(img_data).convert('L')
        orig_w, orig_h = img_raw.size
        max_dim = 1500
        ratio = orig_w / orig_h
        new_w, new_h = (max_dim, int(max_dim / ratio)) if orig_w > orig_h else (int(max_dim * ratio), max_dim)
        
        img = img_raw.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img_np = np.array(img)
        binary = np.where(img_np < 140, 255, 0).astype(np.uint8)

        # 4. Contour Detection
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None: return None

        internal_wall_polys = []
        base_footprints = []
        all_pts_list = []

        for i, h in enumerate(hierarchy[0]):
            if h[3] == -1:  # External contour
                exterior = contours[i].reshape(-1, 2)
                if len(exterior) < 3: continue
                all_pts_list.extend(exterior)
                base_footprints.append(Polygon(shell=exterior))
                
                interiors = []
                child_idx = h[2]
                while child_idx != -1:
                    interior = contours[child_idx].reshape(-1, 2)
                    if len(interior) >= 3:
                        interiors.append(interior)
                        all_pts_list.extend(interior)
                    child_idx = hierarchy[0][child_idx][0]
                
                poly = Polygon(shell=exterior, holes=interiors)
                if not poly.is_valid: poly = make_valid(poly)
                if not poly.is_empty:
                    internal_wall_polys.append(poly.buffer(radius_px, join_style=2, cap_style=2))

        if not internal_wall_polys: return None

        # 5. Framing Logic
        all_pts_np = np.array(all_pts_list)
        min_x, min_y = np.min(all_pts_np, axis=0)
        max_x, max_y = np.max(all_pts_np, axis=0)
        logger.info(f"FRAME BOUNDS: X({min_x:.2f} to {max_x:.2f}), Y({min_y:.2f} to {max_y:.2f})")
        
        # Increase threshold to full wall width (px) for better detection
        side_thresh = radius_px * 2 
        
        sides = {'bottom': [], 'top': [], 'left': [], 'right': []}
        bridge_lines = []

        for poly in internal_wall_polys:
            # Check every point of the polygon exterior to find closest interactions
            coords = list(poly.exterior.coords)
            for pt_coord in coords:
                px, py = pt_coord
                p = Point(pt_coord)
                
                # Use elif to ensure a point only docks to ONE side (prevents diagonal bridges)
                if abs(py - min_y) <= side_thresh: # Bottom
                    sides['bottom'].append((p, Point(px, min_y)))
                elif abs(py - max_y) <= side_thresh: # Top
                    sides['top'].append((p, Point(px, max_y)))
                elif abs(px - min_x) <= side_thresh: # Left
                    sides['left'].append((p, Point(min_x, py)))
                elif abs(px - max_x) <= side_thresh: # Right
                    sides['right'].append((p, Point(max_x, py)))

        frame_segments = []
        for side_name, pairs in sides.items():
            if not pairs: continue
            
            logger.info(f"Side {side_name.upper()}: {len(pairs)} points docked.")

            # 1. Create bridges
            for p, f_pt in pairs:
                bridge = LineString([p, f_pt])
                if bridge.length > 0.01:
                    b_poly = bridge.buffer(radius_px, cap_style=2)
                    bridge_lines.append(b_poly)
                    base_footprints.append(b_poly)

            # 2. Create connecting segment along the frame border
            if len(pairs) >= 2:
                f_points = [pair[1] for pair in pairs]
                if side_name in ['bottom', 'top']:
                    f_points.sort(key=lambda p: p.x)
                    side_line = LineString([f_points[0], f_points[-1]])
                else:
                    f_points.sort(key=lambda p: p.y)
                    side_line = LineString([f_points[0], f_points[-1]])
                
                logger.info(f"Generated {side_name} frame segment: {side_line.length:.2f} px long")
                s_poly = side_line.buffer(radius_px, cap_style=2)
                frame_segments.append(s_poly)
                base_footprints.append(s_poly)

        # 6. Final Wall Geometry
        all_walls_geom = unary_union(internal_wall_polys + bridge_lines + frame_segments)

        # 7. Support Plate
        raw_unified_base = unary_union(base_footprints)
        if not raw_unified_base.is_valid: raw_unified_base = make_valid(raw_unified_base)
        
        base_polys_to_extrude = []
        if isinstance(raw_unified_base, MultiPolygon):
            for p in raw_unified_base.geoms:
                base_polys_to_extrude.append(Polygon(p.exterior))
        else:
            base_polys_to_extrude.append(Polygon(raw_unified_base.exterior))

        # 8. Mesh Generation
        wall_meshes = []
        if hasattr(all_walls_geom, 'geoms'):
            geoms_list = list(all_walls_geom.geoms)
        else:
            geoms_list = [all_walls_geom]

        for gw in geoms_list:
            if gw.area > 0.1:
                wall_meshes.append(trimesh.creation.extrude_polygon(gw, height=wall_h))
        
        combined_walls = trimesh.util.concatenate(wall_meshes)

        if include_base:
            base_meshes = [trimesh.creation.extrude_polygon(bp, height=base_h) for bp in base_polys_to_extrude if bp.area > 0.1]
            combined_base = trimesh.util.concatenate(base_meshes)
            combined_base.apply_translation([0, 0, -base_h])
            final_mesh = trimesh.util.concatenate([combined_walls, combined_base])
        else:
            final_mesh = combined_walls

        # 9. Transformation
        xy_scale = pixel_to_mm * scale_percent
        final_mesh.apply_scale([xy_scale, xy_scale, 1.0])
        c = final_mesh.centroid
        final_mesh.apply_translation([-c[0], -c[1], 0])
        z_min = final_mesh.bounds[0][2]
        final_mesh.apply_translation([0, 0, -z_min])

        # 10. Export
        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        final_mesh.export(temp_path)
        
        return temp_path

    except Exception as e:
        logger.error(f"STL Error: {e}", exc_info=True)
        return None