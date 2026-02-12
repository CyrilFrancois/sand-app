import numpy as np
import trimesh
from PIL import Image, ImageOps, ImageFilter
import io
import os
import uuid
import requests
import cv2
from shapely.geometry import Polygon, MultiPolygon, MultiPoint
from shapely.validation import make_valid
from shapely.ops import unary_union

def generate_stl_from_image(image_source, settings):
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

        # 2. Settings & Calibration
        wall_h = float(settings.get('wallHeight', 3.0))
        base_h = float(settings.get('basePlateThickness', 0.4))
        scale_percent = float(settings.get('scalePercent', 100)) / 100.0
        include_base = settings.get('basePlate', True)
        
        # Calibration constant
        pixel_to_mm = 0.1 * scale_percent

        # 3. Pre-processing
        img = Image.open(img_data).convert('L')
        img = img.resize((1500, 1500), Image.Resampling.LANCZOS)
        img_np = np.array(img)
        binary = np.where(img_np < 140, 255, 0).astype(np.uint8)

        # 4. Outline Detection
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        
        if hierarchy is None:
            return None

        shapely_polys = []
        all_points = [] # To track every point for the global base plate

        for i, h in enumerate(hierarchy[0]):
            if h[3] == -1:  # External contour
                exterior = contours[i].reshape(-1, 2)
                if len(exterior) < 3: continue
                all_points.extend(exterior)
                
                interiors = []
                child_idx = h[2]
                while child_idx != -1:
                    interior = contours[child_idx].reshape(-1, 2)
                    if len(interior) >= 3:
                        interiors.append(interior)
                        all_points.extend(interior)
                    child_idx = hierarchy[0][child_idx][0]
                
                poly = Polygon(shell=exterior, holes=interiors)
                if not poly.is_valid:
                    poly = make_valid(poly)
                
                poly = poly.buffer(0.01)
                if not poly.is_empty:
                    shapely_polys.append(poly)

        if not shapely_polys:
            return None

        # 5. Build 3D Mesh (Walls)
        wall_meshes = []
        for poly in shapely_polys:
            geoms = [poly] if isinstance(poly, Polygon) else list(poly.geoms)
            for g in geoms:
                if g.area > 0.5:
                    # Extrude and force fix to ensure "filled" volume
                    m = trimesh.creation.extrude_polygon(g, height=wall_h)
                    wall_meshes.append(m)

        combined_walls = trimesh.util.concatenate(wall_meshes)
        # Ensure walls are solid/closed
        combined_walls.fill_holes()

        # 6. Global Support Plate (Convex Hull approach)
        if include_base and all_points:
            # Create a single geometry from ALL points of ALL objects
            points_geom = MultiPoint(all_points)
            # Convex hull finds the "most outside points" and draws a perimeter
            global_base_poly = points_geom.convex_hull
            
            # Buffer it slightly so it extends beyond the objects
            global_base_poly = global_base_poly.buffer(5.0) 
            
            # Extrude the base downward
            base_mesh = trimesh.creation.extrude_polygon(global_base_poly, height=base_h)
            base_mesh.apply_translation([0, 0, -base_h])
            
            final_mesh = trimesh.util.concatenate([combined_walls, base_mesh])
        else:
            final_mesh = combined_walls

        # 7. Final Scale & Bed Placement
        # Scale everything to the requested physical size
        final_mesh.apply_scale(pixel_to_mm)
        
        # Center the model
        final_mesh.apply_translation(-final_mesh.centroid)
        # Place flat on Z=0
        z_min = final_mesh.bounds[0][2]
        final_mesh.apply_translation([0, 0, -z_min])

        # 8. Export
        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        final_mesh.export(temp_path)
        
        return temp_path

    except Exception as e:
        print(f"STL Error: {e}")
        return None