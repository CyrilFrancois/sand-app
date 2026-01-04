import numpy as np
import trimesh
from PIL import Image, ImageOps, ImageFilter
import io
import os
import uuid

def generate_stl_from_image(image_bytes, settings):
    try:
        # 1. Load and Anti-Alias
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        
        # Settings
        wall_h = float(settings.get('wallHeight', 3.0))
        base_plate_h = float(settings.get('basePlateThickness', 0.3))
        scale_percent = float(settings.get('scalePercent', 100))
        
        # 2. SMOOTHING: This is the key to removing the "stairs"
        # We upsample the image and apply a blur to interpolate between pixels
        process_size = 1200 
        img = img.resize((process_size, process_size), Image.Resampling.LANCZOS)
        
        # Apply a subtle blur to "melt" the pixel corners into curves
        img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
        
        img = ImageOps.invert(img)
        width, height = img.size
        data = np.array(img) / 255.0

        # 3. Create Smooth Mesh Grid
        # We use a step (e.g., skip 2 pixels) to create larger triangles
        # which further smooths out the micro-stepping
        step = 2
        vertices = []
        cols = range(0, width, step)
        rows = range(0, height, step)
        
        # Map pixels to vertices
        for y in rows:
            for x in cols:
                # We use a power function to sharpen the top of the wall 
                # while keeping the base smooth
                z = (data[y, x] ** 1.5) * wall_h
                vertices.append([x, y, z])
        
        vertices = np.array(vertices)
        
        # 4. Triangulation
        faces = []
        num_cols = len(cols)
        num_rows = len(rows)
        for r in range(num_rows - 1):
            for c in range(num_cols - 1):
                v0 = r * num_cols + c
                v1 = v0 + 1
                v2 = v0 + num_cols
                v3 = v2 + 1
                faces.append([v0, v2, v1])
                faces.append([v1, v2, v3])
        
        surface_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

        # 5. Base Plate and Scaling
        if settings.get('basePlate', True):
            # Create a base slightly larger to ensure clean edges
            base = trimesh.creation.box(extents=(width, height, base_plate_h))
            base.apply_translation([(width-step)/2, (height-step)/2, -base_plate_h/2])
            combined = trimesh.util.concatenate([surface_mesh, base])
        else:
            combined = surface_mesh

        # Physical Scaling (Adjust 0.08 to match your real-world print size)
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