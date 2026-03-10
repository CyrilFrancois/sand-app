import numpy as np

import trimesh

from PIL import Image

import io

import os

import uuid

import requests

import cv2

import logging

from shapely.geometry import Polygon, MultiPolygon, LineString

from shapely.validation import make_valid

from shapely.ops import unary_union



# Set up logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("sand-backend")



def generate_stl_from_image(image_source, settings):

    logger.info("--- Uniform Wall Width STL Generation ---")

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

        # The half-width radius for the buffer

        radius_px = (target_wall_width_mm / pixel_to_mm) / 2.0



        for i, h in enumerate(hierarchy[0]):

            if h[3] == -1:  # External contour

                exterior = contours[i].reshape(-1, 2)

                if len(exterior) < 3: continue

               

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



                # Internal Walls: Forced uniform width via Dilated Boundary

                # We buffer the boundary of the stroke to ensure it is exactly X mm wide

                if not poly.is_empty:

                    stroke_wall = poly.buffer(radius_px, join_style=2, cap_style=2)

                    internal_wall_polys.append(stroke_wall)



        if not internal_wall_polys: return None



        # 5. Support Shape (Join & Fill Holes)

        raw_unified_base = unary_union(base_footprints)

        bridge_dist = 50

        envelope_poly = raw_unified_base.buffer(bridge_dist).buffer(-bridge_dist)

       

        # ENSURE NO HOLES: Reconstruct using only exterior shells

        if not envelope_poly.is_empty:

            if isinstance(envelope_poly, MultiPolygon):

                envelope_poly = MultiPolygon([Polygon(p.exterior) for p in envelope_poly.geoms])

            else:

                envelope_poly = Polygon(envelope_poly.exterior)



        if not envelope_poly.is_valid:

            envelope_poly = make_valid(envelope_poly)



        # 6. Uniform External Wall Generation

        # We extract the perimeter of the support plate and expand it

        # as a solid line to ensure thickness is consistent everywhere.

        external_walls = []

        if isinstance(envelope_poly, MultiPolygon):

            exteriors = [p.exterior for p in envelope_poly.geoms]

        else:

            exteriors = [envelope_poly.exterior]



        for ext in exteriors:

            # Buffer the line itself (LineString) to create a wall of uniform thickness

            wall_geom = ext.buffer(radius_px, join_style=2, cap_style=2)

            external_walls.append(wall_geom)



        # 7. Combine All Walls

        all_walls_geom = unary_union(internal_wall_polys + external_walls)

       

        wall_meshes = []

        geoms_w = [all_walls_geom] if isinstance(all_walls_geom, (Polygon, MultiPolygon)) else [all_walls_geom]

        if hasattr(all_walls_geom, 'geoms'):

            geoms_list = list(all_walls_geom.geoms)

        else:

            geoms_list = [all_walls_geom]



        for gw in geoms_list:

            if gw.area > 0.1:

                wall_meshes.append(trimesh.creation.extrude_polygon(gw, height=wall_h))

       

        combined_walls = trimesh.util.concatenate(wall_meshes)



        # 8. Support Plate Extrusion

        if include_base:

            base_mesh = trimesh.creation.extrude_polygon(envelope_poly, height=base_h)

            base_mesh.apply_translation([0, 0, -base_h])

            final_mesh = trimesh.util.concatenate([combined_walls, base_mesh])

        else:

            final_mesh = combined_walls



        # 9. Final Transformation

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