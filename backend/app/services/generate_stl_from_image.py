import numpy as np
import trimesh
from PIL import Image
import io
import os
import uuid
import requests
import cv2
import logging
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid
from shapely.ops import unary_union

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sand-backend")

def generate_stl_from_image(image_source, settings):
    logger.info("--- New STL Generation Request ---")
    # Log all parameters for debugging
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

        # 2. Extract and Sanitize Settings
        wall_h = float(settings.get('wallHeight', 3.0))
        base_h = float(settings.get('basePlateThickness', 0.4))
        target_wall_width_mm = float(settings.get('wallThickness', 1.0))
        scale_percent = float(settings.get('scalePercent', 100)) / 100.0
        include_base = settings.get('basePlate', True)
        
        # Internal pixel calibration (0.1mm baseline)
        pixel_to_mm = 0.1 

        # 3. Load & Aspect Ratio Preservation
        img_raw = Image.open(img_data).convert('L')
        orig_w, orig_h = img_raw.size
        
        max_dim = 1500
        ratio = orig_w / orig_h
        if orig_w > orig_h:
            new_w, new_h = max_dim, int(max_dim / ratio)
        else:
            new_h, new_w = max_dim, int(max_dim * ratio)
            
        img = img_raw.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img_np = np.array(img)
        binary = np.where(img_np < 140, 255, 0).astype(np.uint8)

        # 4. Hierarchical Contour Detection
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        
        if hierarchy is None:
            logger.error("No contours found.")
            return None

        final_wall_polys = []
        base_outline_polys = []

        # Convert target mm width to pixel units for Shapely processing
        # This is the 'radius' for buffering
        target_buffer_px = (target_wall_width_mm / pixel_to_mm) / 2.0

        for i, h in enumerate(hierarchy[0]):
            if h[3] == -1:  # External contour
                exterior = contours[i].reshape(-1, 2)
                if len(exterior) < 3: continue
                
                interiors = []
                child_idx = h[2]
                while child_idx != -1:
                    interior = contours[child_idx].reshape(-1, 2)
                    if len(interior) >= 3:
                        interiors.append(interior)
                    child_idx = hierarchy[0][child_idx][0]
                
                poly = Polygon(shell=exterior, holes=interiors)
                if not poly.is_valid: poly = make_valid(poly)

                # --- INTELLIGENT WALL THINNING ---
                # Instead of skeletonization, we use a "Negative-Positive Buffer"
                # This shrinks thick lines to their center, then expands to exactly target_wall_width
                # Thin lines that would disappear are protected.
                shrunk = poly.buffer(-target_buffer_px)
                if shrunk.is_empty or shrunk.area < 1.0:
                    # If it's already thinner than target, keep original or expand slightly
                    final_wall = poly
                else:
                    # Re-expand the "core" to the exact desired width
                    final_wall = shrunk.buffer(target_buffer_px)

                final_wall_polys.append(final_wall)
                # For the base, we take the solid version (shell only)
                base_outline_polys.append(Polygon(shell=exterior))

        if not final_wall_polys:
            return None

        # 5. Build 3D Wall Meshes
        wall_meshes = []
        unified_walls = unary_union(final_wall_polys)
        
        geoms_w = [unified_walls] if isinstance(unified_walls, Polygon) else list(unified_walls.geoms)
        for gw in geoms_w:
            if gw.area > 0.1:
                m = trimesh.creation.extrude_polygon(gw, height=wall_h)
                wall_meshes.append(m)
        
        combined_walls = trimesh.util.concatenate(wall_meshes)

        # 6. Unified Global Support Plate (One Shape)
        if include_base and base_outline_polys:
            # Union all footprints into one single continuous shape
            unified_base_geom = unary_union(base_outline_polys)
            
            base_parts = []
            geoms_b = [unified_base_geom] if isinstance(unified_base_geom, Polygon) else list(unified_base_geom.geoms)
            for gb in geoms_b:
                bm = trimesh.creation.extrude_polygon(gb, height=base_h)
                bm.apply_translation([0, 0, -base_h])
                base_parts.append(bm)
            
            final_mesh = trimesh.util.concatenate([combined_walls] + base_parts)
        else:
            final_mesh = combined_walls

        # 7. Scaling (X/Y scaled, Z constant)
        xy_scale = pixel_to_mm * scale_percent
        final_mesh.apply_scale([xy_scale, xy_scale, 1.0])
        
        # 8. Centering & Placement
        c = final_mesh.centroid
        final_mesh.apply_translation([-c[0], -c[1], 0])
        z_min = final_mesh.bounds[0][2]
        final_mesh.apply_translation([0, 0, -z_min])

        # 9. Export
        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        final_mesh.export(temp_path)
        
        logger.info(f"STL Generation Successful: {temp_path}")
        return temp_path

    except Exception as e:
        logger.error(f"STL Generation Failed: {e}", exc_info=True)
        return None