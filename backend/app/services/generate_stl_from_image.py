import numpy as np
import trimesh
from PIL import Image
import io
import os
import uuid
import requests
import cv2
import logging
from shapely.geometry import Polygon, MultiPolygon, MultiPoint, LineString
from shapely.validation import make_valid
from shapely.ops import unary_union

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sand-backend")

def generate_stl_from_image(image_source, settings):
    logger.info("--- Refined STL Generation Request ---")
    for key, value in settings.items():
        logger.info(f"Param: {key} = {value}")

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
        target_buffer_px = (target_wall_width_mm / pixel_to_mm) / 2.0

        for i, h in enumerate(hierarchy[0]):
            if h[3] == -1:  # External contour
                exterior = contours[i].reshape(-1, 2)
                if len(exterior) < 3: continue
                
                # Store for base calculation
                base_footprints.append(Polygon(shell=exterior))
                
                interiors = []
                child_idx = h[2]
                while child_idx != -1:
                    interior = contours[child_idx].reshape(-1, 2)
                    if len(interior) >= 3:
                        interiors.append(interior)
                    child_idx = hierarchy[0][child_idx][0]
                
                poly = Polygon(shell=exterior, holes=interiors)
                if not poly.is_valid: poly = make_valid(poly)

                # Ensure line survival: Positive buffer first
                # join_style=2 (mitre) or join_style=1 (round) to prevent thinning
                protected_poly = poly.buffer(target_buffer_px, join_style=2)
                internal_wall_polys.append(protected_poly)

        if not internal_wall_polys: return None

        # 5. Unified Support Shape (Curve-following + No Holes)
        raw_unified_base = unary_union(base_footprints)
        bridge_dist = 50 
        envelope_poly = raw_unified_base.buffer(bridge_dist).buffer(-bridge_dist)
        
        # STEP: Fill all internal holes for the support plate
        if not envelope_poly.is_empty:
            if isinstance(envelope_poly, MultiPolygon):
                # Process each part: Create a new polygon using only the exterior shell
                envelope_poly = MultiPolygon([Polygon(p.exterior) for p in envelope_poly.geoms])
            else:
                envelope_poly = Polygon(envelope_poly.exterior)

        if not envelope_poly.is_valid: 
            envelope_poly = make_valid(envelope_poly)

        # 6. Generate Uniform External Boundary Wall
        # We buffer the shell of the support plate to get the outer containment wall
        # Using join_style=2 (mitre) ensures sharp corners and consistent width in slicers
        boundary_line = envelope_poly.exterior
        external_boundary_wall_poly = boundary_line.buffer(target_buffer_px, join_style=2, cap_style=2)

        # 7. Combine All Wall Geometries
        all_walls_geom = unary_union(internal_wall_polys + [external_boundary_wall_poly])
        
        wall_meshes = []
        geoms_w = [all_walls_geom] if isinstance(all_walls_geom, Polygon) else list(all_walls_geom.geoms)
        for gw in geoms_w:
            if gw.area > 0.1:
                wall_meshes.append(trimesh.creation.extrude_polygon(gw, height=wall_h))
        
        combined_walls = trimesh.util.concatenate(wall_meshes)

        # 8. Support Plate (Solid Footprint)
        if include_base:
            base_mesh = trimesh.creation.extrude_polygon(envelope_poly, height=base_h)
            base_mesh.apply_translation([0, 0, -base_h])
            final_mesh = trimesh.util.concatenate([combined_walls, base_mesh])
        else:
            final_mesh = combined_walls

        # 9. Scaling (X/Y scaled, Z constant)
        xy_scale = pixel_to_mm * scale_percent
        final_mesh.apply_scale([xy_scale, xy_scale, 1.0])
        
        # 10. Centering & Placement
        c = final_mesh.centroid
        final_mesh.apply_translation([-c[0], -c[1], 0])
        z_min = final_mesh.bounds[0][2]
        final_mesh.apply_translation([0, 0, -z_min])

        # 11. Export
        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        final_mesh.export(temp_path)
        
        logger.info(f"STL Created successfully: {temp_path}")
        return temp_path

    except Exception as e:
        logger.error(f"STL Error: {e}", exc_info=True)
        return None