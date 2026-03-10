import numpy as np
import trimesh
from PIL import Image
import io
import os
import uuid
import requests
import cv2
import logging
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.validation import make_valid
from shapely.ops import unary_union

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sand-backend")

def generate_stl_from_image(image_source, settings):
    logger.info(f"Incoming Settings: {settings}")
    
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

        # --- DYNAMIC THICKNESS COMPENSATION ---
        dist_transform = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
        detected_thickness = np.percentile(dist_transform[dist_transform > 0], 50) * 2.0 if np.any(binary) else 0
        frame_radius_px = radius_px + (detected_thickness / 2.0)

        # 4. Contour Detection
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None: return None

        internal_wall_polys = []
        all_pts_list = []

        for i, h in enumerate(hierarchy[0]):
            if h[3] == -1:
                exterior = contours[i].reshape(-1, 2)
                if len(exterior) < 3: continue
                all_pts_list.extend(exterior)
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
        side_thresh = max(detected_thickness * 1.5, 10.0)
        max_touch_span = max(detected_thickness * 4.0, 20.0)

        sides = {'bottom': [], 'top': [], 'left': [], 'right': []}
        for poly in internal_wall_polys:
            coords = list(poly.exterior.coords)
            for side_name in ['bottom', 'top', 'left', 'right']:
                current_segment = []
                for pt in coords:
                    px, py = pt
                    hit = (side_name == 'bottom' and abs(py - min_y) <= side_thresh) or \
                          (side_name == 'top' and abs(py - max_y) <= side_thresh) or \
                          (side_name == 'left' and abs(px - min_x) <= side_thresh) or \
                          (side_name == 'right' and abs(px - max_x) <= side_thresh)
                    if hit: current_segment.append(pt)
                    else:
                        if current_segment:
                            seg_np = np.array(current_segment)
                            if np.linalg.norm(seg_np[0] - seg_np[-1]) < max_touch_span:
                                mid = seg_np[len(seg_np)//2]
                                snap = Point(mid[0], min_y) if side_name == 'bottom' else \
                                       Point(mid[0], max_y) if side_name == 'top' else \
                                       Point(min_x, mid[1]) if side_name == 'left' else Point(max_x, mid[1])
                                sides[side_name].append((Point(mid), snap))
                            current_segment = []

        frame_segments = []
        for side_name, pairs in sides.items():
            if len(pairs) >= 2:
                f_pts = [pair[1] for pair in pairs]
                f_pts.sort(key=lambda p: p.x if side_name in ['bottom', 'top'] else p.y)
                side_line = LineString([f_pts[0], f_pts[-1]])
                frame_segments.append(side_line.buffer(frame_radius_px, cap_style=2, join_style=2))

        # 6. Final Wall Geometry
        all_walls_geom = unary_union(internal_wall_polys + frame_segments)

        # 7. Support Plate (EXACT CONCAVE FOOTPRINT)
        base_meshes = []
        if include_base:
            # Step A: Take all geometry (walls and frames)
            footprint_parts = []
            geoms_to_process = all_walls_geom.geoms if hasattr(all_walls_geom, 'geoms') else [all_walls_geom]
            
            for g in geoms_to_process:
                if isinstance(g, Polygon) and not g.is_empty:
                    # Step B: Create a SOLID version of the shape (fill holes/interior)
                    # by only taking the exterior ring as a new Polygon
                    footprint_parts.append(Polygon(g.exterior))
            
            # Step C: Union them together to form the continuous base
            exact_support_poly = unary_union(footprint_parts)
            
            if not exact_support_poly.is_empty:
                # Handle potential multipolygons from the union
                base_polys = exact_support_poly.geoms if hasattr(exact_support_poly, 'geoms') else [exact_support_poly]
                for bp in base_polys:
                    if bp.area > 0.1:
                        base_meshes.append(trimesh.creation.extrude_polygon(bp, height=base_h))

        # 8. Mesh Generation
        wall_meshes = []
        geoms_list = all_walls_geom.geoms if hasattr(all_walls_geom, 'geoms') else [all_walls_geom]
        for gw in geoms_list:
            if isinstance(gw, Polygon) and gw.area > 0.1:
                wall_meshes.append(trimesh.creation.extrude_polygon(gw, height=wall_h))
        
        combined_walls = trimesh.util.concatenate(wall_meshes)

        if base_meshes:
            combined_base = trimesh.util.concatenate(base_meshes)
            combined_base.apply_translation([0, 0, -base_h])
            final_mesh = trimesh.util.concatenate([combined_walls, combined_base])
        else:
            final_mesh = combined_walls

        # 9. Transformation
        xy_scale = pixel_to_mm * scale_percent
        final_mesh.apply_scale([xy_scale, xy_scale, 1.0])
        final_mesh.apply_translation(-final_mesh.centroid)
        final_mesh.apply_translation([0, 0, -final_mesh.bounds[0][2]])

        # 10. Export
        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        final_mesh.export(temp_path)
        return temp_path

    except Exception as e:
        logger.error(f"STL Error: {e}", exc_info=True)
        return None