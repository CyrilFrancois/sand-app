import numpy as np
import trimesh
from PIL import Image, ImageOps, ImageFilter
import io
import os
import uuid

def generate_stl_from_image(image_bytes, settings):
    try:
        # 1. Load and Smooth (LANCZOS + Gaussian is vital for curves)
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        
        wall_h = float(settings.get('wallHeight', 3.0))
        base_plate_h = float(settings.get('basePlateThickness', 0.4))
        scale_percent = float(settings.get('scalePercent', 100))
        include_base = settings.get('basePlate', True)
        
        process_size = 1200 
        img = img.resize((process_size, process_size), Image.Resampling.LANCZOS)
        
        # We use a slightly stronger blur for the "No Plate" mode 
        # to ensure the edges are super smooth
        img = img.filter(ImageFilter.GaussianBlur(radius=2.0))
        
        img = ImageOps.invert(img)
        width, height = img.size
        data = np.array(img) / 255.0

        # 2. Create the smooth vertex grid
        step = 2
        cols = np.arange(0, width, step)
        rows = np.arange(0, height, step)
        
        # Efficiently create grid using meshgrid
        x_grid, y_grid = np.meshgrid(cols, rows)
        z_grid = (data[rows[:, None], cols] ** 1.5) * wall_h
        
        vertices = np.stack([x_grid.flatten(), y_grid.flatten(), z_grid.flatten()], axis=1)

        # 3. Create full mesh faces first
        num_cols = len(cols)
        num_rows = len(rows)
        faces = []
        for r in range(num_rows - 1):
            for c in range(num_cols - 1):
                v0 = r * num_cols + c
                v1 = v0 + 1
                v2 = v0 + num_cols
                v3 = v2 + 1
                faces.append([v0, v2, v1])
                faces.append([v1, v2, v3])
        
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

        # 4. THE FIX: Soft Masking
        # Instead of a hard cut at 0, we look for very low intensity areas
        # and remove those faces. This keeps the "sloped" edges of the curves.
        if not include_base:
            # Calculate intensity at the center of each face
            face_vertices = mesh.vertices[mesh.faces]
            # Get the original image coordinates for each face
            face_centers_x = face_vertices[:, :, 0].mean(axis=1).astype(int)
            face_centers_y = face_vertices[:, :, 1].mean(axis=1).astype(int)
            
            # Mask out faces where the image is nearly black (the background)
            # A very low threshold (0.01) ensures we keep the smooth "slopes"
            mask = data[face_centers_y, face_centers_x] > 0.02
            mesh.update_faces(mask)
            
            # Remove vertices that are no longer connected to any face
            mesh.remove_unreferenced_vertices()

        # 5. Base Plate & Scaling
        if include_base:
            base = trimesh.creation.box(extents=(width, height, base_plate_h))
            base.apply_translation([(width-step)/2, (height-step)/2, -base_plate_h/2])
            combined = trimesh.util.concatenate([mesh, base])
        else:
            combined = mesh

        # Apply final scaling
        mm_per_pixel = 0.08 * (scale_percent / 100.0)
        combined.apply_scale(mm_per_pixel)

        # 6. Export
        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        temp_path = os.path.join(output_dir, f"sand_art_{uuid.uuid4().hex[:8]}.stl")
        combined.export(temp_path)
        
        return temp_path

    except Exception as e:
        print(f"STL Error: {e}")
        return None