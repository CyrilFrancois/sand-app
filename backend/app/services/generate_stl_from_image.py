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
from skimage.morphology import skeletonize 

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
        base_h = float(settings.get('basePlateThickness', 0.12))
        target_wall_width_mm = float(settings.get('wallThickness', 0.12))
        scale_percent = float(settings.get('scalePercent', 100)) / 100.0
        include_base = settings.get('basePlate', True)
        
        pixel_to_mm = 0.1
        target_radius_px = (target_wall_width_mm / pixel_to_mm) / 2.0

        # 3. Pre-processing & Skeletonization
        img_raw = Image.open(img_data).convert('L')
        orig_w, orig_h = img_raw.size
        max_dim = 1500
        ratio = orig_w / orig_h
        new_w, new_h = (max_dim, int(max_dim / ratio)) if orig_w > orig_h else (int(max_dim * ratio), max_dim)
        img = img_raw.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img_np = np.array(img)
        
        binary_bool = (img_np < 140).astype(np.uint8)
        skeleton_img = skeletonize(binary_bool).astype(np.uint8) * 255
        
        # --- CORE FIX: DANGLING POINT DETECTION ---
        # A dangling point (endpoint) in a skeleton has exactly one 8-neighbor
        kernel = np.array([[1, 1, 1], [1, 10, 1], [1, 11, 1]], dtype=np.uint8) # Dummy for logic
        # We use a hit-or-miss approach or simple neighbor count
        skel_idx = np.where(skeleton_img > 0)
        endpoints = []
        for r, c in zip(skel_idx[0], skel_idx[1]):
            # Count neighbors in 3x3 area
            neighborhood = (skeleton_img[max(0, r-1):r+2, max(0, c-1):c+2] > 0).astype(int)
            if np.sum(neighborhood) == 2: # 1 for the point itself, 1 for the neighbor
                endpoints.append((float(c), float(r)))

        # 4. Contour Detection on Skeleton
        contours, _ = cv2.findContours(skeleton_img, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        internal_wall_polys = []
        all_pts_list = []

        for cnt in contours:
            pts = cnt.reshape(-1, 2).astype(float)
            if len(pts) < 2: continue
            all_pts_list.extend([tuple(p) for p in pts])
            
            line = LineString(pts)
            if not line.is_valid: line = make_valid(line)
            
            buffered = line.buffer(target_radius_px, join_style=2, cap_style=2)
            if isinstance(buffered, MultiPolygon):
                internal_wall_polys.extend(list(buffered.geoms))
            elif isinstance(buffered, Polygon):
                internal_wall_polys.append(buffered)

        if not internal_wall_polys: return None

        # 5. FIXED Framing Logic: Bridge only Dangling Endpoints near edges
        all_pts_np = np.array(all_pts_list)
        min_x, min_y = np.min(all_pts_np, axis=0)
        max_x, max_y = np.max(all_pts_np, axis=0)
        
        edge_threshold = max(target_radius_px * 2.5, 6.0)
        frame_segments = []
        
        boundaries = {
            'bottom': {'idx': 1, 'val': min_y, 'sort': 0},
            'top':    {'idx': 1, 'val': max_y, 'sort': 0},
            'left':   {'idx': 0, 'val': min_x, 'sort': 1},
            'right':  {'idx': 0, 'val': max_x, 'sort': 1}
        }

        for side, cfg in boundaries.items():
            # Only consider "endpoints" for framing, not every point on a curve
            relevant_endpoints = [p for p in endpoints if abs(p[cfg['idx']] - cfg['val']) <= edge_threshold]
            
            if len(relevant_endpoints) >= 2:
                relevant_endpoints.sort(key=lambda x: x[cfg['sort']])
                p1, p2 = relevant_endpoints[0], relevant_endpoints[-1]
                
                # Construct frame line at the actual bounding limit
                if side in ['bottom', 'top']:
                    line_pts = [(p1[0], cfg['val']), (p2[0], cfg['val'])]
                else:
                    line_pts = [(cfg['val'], p1[1]), (cfg['val'], p2[1])]
                
                side_line = LineString(line_pts)
                frame_segments.append(side_line.buffer(target_radius_px, cap_style=2, join_style=2))

        # 6. Combine Geometry
        all_walls_geom = unary_union(internal_wall_polys + frame_segments)

        # 7. Support Plate (Dynamic solidification based on wall thickness)
        base_meshes = []
        if include_base:
            footprint_parts = []
            # Access the combined wall geometry (internal walls + frame)
            geoms_to_process = all_walls_geom.geoms if isinstance(all_walls_geom, MultiPolygon) else [all_walls_geom]
            
            # Use a small epsilon buffer (50% of wall thickness) to bridge precision gaps
            epsilon = target_radius_px * 0.5
            
            for g in geoms_to_process:
                if isinstance(g, Polygon) and not g.is_empty:
                    # Dilate slightly, take the boundary, and fill it
                    # This ensures thin 0.3mm walls are treated as solid footprints
                    filled = g.buffer(epsilon).exterior
                    if filled:
                        footprint_parts.append(Polygon(filled))
            
            # Merge all parts and shrink back by the epsilon to match wall edges perfectly
            exact_support_poly = unary_union(footprint_parts).buffer(-epsilon)
            
            if not exact_support_poly.is_empty:
                base_polys = exact_support_poly.geoms if isinstance(exact_support_poly, MultiPolygon) else [exact_support_poly]
                for bp in base_polys:
                    if bp.area > 0.01: # Lowered threshold for very thin details
                        try:
                            base_meshes.append(trimesh.creation.extrude_polygon(bp, height=base_h))
                        except Exception: continue

        # 8. Final STL Assembly
        wall_meshes = []
        final_geoms = all_walls_geom.geoms if isinstance(all_walls_geom, MultiPolygon) else [all_walls_geom]
        for gw in final_geoms:
            if isinstance(gw, Polygon) and gw.area > 0.1:
                try:
                    wall_meshes.append(trimesh.creation.extrude_polygon(gw, height=wall_h))
                except Exception: continue
        
        if not wall_meshes: return None
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

        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        final_mesh.export(temp_path)
        return temp_path

    except Exception as e:
        logger.error(f"STL Error: {e}", exc_info=True)
        return None