import numpy as np
import trimesh
from PIL import Image, ImageOps, ImageFilter
import io
import os
import uuid
import requests

def generate_stl_from_image(image_source, settings):
    """
    image_source can be: 
    1. A URL string (http...)
    2. A local file path string (/tmp/...)
    3. Raw bytes
    """
    try:
        # --- NEW: Robust Image Loading ---
        if isinstance(image_source, str):
            if image_source.startswith('http'):
                # Download from OpenAI/Web
                response = requests.get(image_source)
                img_data = io.BytesIO(response.content)
            else:
                # Load from local disk (Direct Upload)
                if os.path.exists(image_source):
                    with open(image_source, 'rb') as f:
                        img_data = io.BytesIO(f.read())
                else:
                    raise FileNotFoundError(f"Local image path not found: {image_source}")
        else:
            # Assume raw bytes
            img_data = io.BytesIO(image_source)

        # 1. Load and Smooth
        img = Image.open(img_data).convert('L')
        
        wall_h = float(settings.get('wallHeight', 3.0))
        base_plate_h = float(settings.get('basePlateThickness', 0.4))
        scale_percent = float(settings.get('scalePercent', 100))
        include_base = settings.get('basePlate', True)
        
        # High-quality resize for smooth curves
        process_size = 1200 
        img = img.resize((process_size, process_size), Image.Resampling.LANCZOS)
        
        # Blur radius adjusted for organic feel
        img = img.filter(ImageFilter.GaussianBlur(radius=2.0))
        
        img = ImageOps.invert(img)
        width, height = img.size
        data = np.array(img) / 255.0

        # 2. Create the smooth vertex grid
        step = 2
        cols = np.arange(0, width, step)
        rows = np.arange(0, height, step)
        
        x_grid, y_grid = np.meshgrid(cols, rows)
        # Power function (1.5) keeps the base wide and the top sharp
        z_grid = (data[rows[:, None], cols] ** 1.5) * wall_h
        
        vertices = np.stack([x_grid.flatten(), y_grid.flatten(), z_grid.flatten()], axis=1)

        # 3. Create full mesh faces
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

        # 4. Soft Masking (Crucial for "No Plate" smooth edges)
        if not include_base:
            face_vertices = mesh.vertices[mesh.faces]
            face_centers_x = face_vertices[:, :, 0].mean(axis=1).astype(int)
            face_centers_y = face_vertices[:, :, 1].mean(axis=1).astype(int)
            
            # Use a low threshold to preserve the anti-aliased edges
            mask = data[face_centers_y, face_centers_x] > 0.02
            mesh.update_faces(mask)
            mesh.remove_unreferenced_vertices()

        # 5. Base Plate & Scaling
        if include_base:
            base = trimesh.creation.box(extents=(width, height, base_plate_h))
            base.apply_translation([(width-step)/2, (height-step)/2, -base_plate_h/2])
            combined = trimesh.util.concatenate([mesh, base])
        else:
            combined = mesh

        # Apply final scaling (0.08 mm per pixel baseline)
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