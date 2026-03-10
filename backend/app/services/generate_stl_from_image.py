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
    logger.info("--- Bounding Frame & Uniform Wall Generation ---")
    
    try:
        # 1. Image Loading & Pre-processing
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

        img_raw = Image.open(img_data).convert('L')
        orig_w, orig_h = img_raw.size
        max_dim = 1500
        ratio = orig_w / orig_h
        new_w, new_h = (max_dim, int(max_dim / ratio)) if orig_w > orig_h else (int(max_dim * ratio), max_dim)
        
        img = img_raw.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img_np = np.array(img)
        binary = np.where(img_np < 140, 255, 0).astype(np.uint8)

        # 3. Contour Detection
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None: return None

        all_paths = []
        all_points = []

        for i, h in enumerate(hierarchy[0]):
            if h[3] == -1:  # External contour
                pts = contours[i].reshape(-1, 2)
                if len(pts) < 2: continue
                all_paths.append(LineString(pts))
                all_points.extend(pts)

        if not all_paths: return None

        # 4. The Imaginary Frame (Bounding Box)
        all_pts_np = np.array(all_points)
        min_x, min_y = np.min(all_pts_np, axis=0) - 5 # 5px padding
        max_x, max_y = np.max(all_pts_np, axis=0) + 5
        frame_rect = box(min_x, min_y, max_x, max_y)
        frame_border = frame_rect.exterior # The LineString of the box

        # 5. Logical Closing: Connect endpoints to the frame
        closing_segments = []
        for path in all_paths:
            # Check the start and end point of each line
            for end_pt_coords in [path.coords[0], path.coords[-1]]:
                p = Point(end_pt_coords)
                # Find the closest point on the frame border
                proj_dist = frame_border.project(p)
                closest_point_on_frame = frame_border.interpolate(proj_dist)
                
                # Create a bridge line from the dangling end to the frame
                bridge = LineString([p, closest_point_on_frame])
                closing_segments.append(bridge)

        # 6. Create UNIFORM Walls
        # We combine drawing paths, bridges, and the frame itself
        final_linestrings = all_paths + closing_segments + [frame_border]
        
        # Buffer every LineString. This is the SECRET to uniform thickness.
        # It creates a "ribbon" of exactly target_wall_width around every line.
        wall_polygons = [ls.buffer(radius_px, join_style=2, cap_style=2) for ls in final_linestrings]
        unified_walls_geom = unary_union(wall_polygons)

        # 7. Create the Support Plate (Solid Bounding Box)
        # Instead of curved islands, we use the frame we calculated
        if include_base:
            plate_geom = Polygon(frame_border) # Filled rectangle
            plate_mesh = trimesh.creation.extrude_polygon(plate_geom, height=base_h)
            plate_mesh.apply_translation([0, 0, -base_h])
        
        # 8. Extrude Walls
        wall_meshes = []
        if isinstance(unified_walls_geom, Polygon):
            geoms = [unified_walls_geom]
        else:
            geoms = unified_walls_geom.geoms

        for g in geoms:
            if g.area > 0.1:
                wall_meshes.append(trimesh.creation.extrude_polygon(g, height=wall_h))
        
        combined_walls = trimesh.util.concatenate(wall_meshes)

        # 9. Combine and Finalize
        if include_base:
            final_mesh = trimesh.util.concatenate([combined_walls, plate_mesh])
        else:
            final_mesh = combined_walls

        # 10. Transform & Export
        xy_scale = pixel_to_mm * scale_percent
        final_mesh.apply_scale([xy_scale, xy_scale, 1.0])
        
        # Center the model
        c = final_mesh.centroid
        final_mesh.apply_translation([-c[0], -c[1], 0])
        z_min = final_mesh.bounds[0][2]
        final_mesh.apply_translation([0, 0, -z_min])

        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        final_mesh.export(temp_path)
        
        return temp_path

    except Exception as e:
        logger.error(f"STL Error: {e}", exc_info=True)
        return None