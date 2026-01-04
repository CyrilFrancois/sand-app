import numpy as np
import trimesh
from PIL import Image, ImageOps
import io
import os
import uuid

def generate_stl_from_image(image_bytes, settings):
    try:
        # 1. Load and Pre-process
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        
        # Extract new high-precision settings
        wall_h = float(settings.get('wallHeight', 3.0))
        wall_t = float(settings.get('wallThickness', 0.3))
        base_plate_h = float(settings.get('basePlateThickness', 0.3))
        has_base_plate = bool(settings.get('basePlate', True))
        scale_percent = float(settings.get('scalePercent', 100))
        
        # 2. Resolution vs. Pixelation
        # Instead of 300px, we use a higher density for smoothness
        # But we blur slightly to prevent jagged "staircase" edges
        max_dim = 800 
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        img = ImageOps.invert(img) # Invert so lines (black) become high points
        
        width, height = img.size
        data = np.array(img) / 255.0  # Normalize 0.0 to 1.0

        # 3. Create a Heightmap Mesh
        # This creates a grid of vertices directly mapped to pixel intensity
        vertices = []
        for y in range(height):
            for x in range(width):
                # Z height is determined by the "blackness" of the line
                # If it's a line, height = wall_h. If background, height = 0.
                z = data[y, x] * wall_h
                vertices.append([x, y, z])
        
        vertices = np.array(vertices)

        # 4. Generate Faces (Triangulation)
        faces = []
        for y in range(height - 1):
            for x in range(width - 1):
                v0 = y * width + x
                v1 = v0 + 1
                v2 = v0 + width
                v3 = v2 + 1
                faces.append([v0, v2, v1])
                faces.append([v1, v2, v3])
        
        # Create the top surface mesh
        surface_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

        # 5. Add the Base Plate
        if has_base_plate:
            # Create a box exactly the size of the image
            base = trimesh.creation.box(extents=(width-1, height-1, base_plate_h))
            # Move base so it sits under the surface (Z goes from -thickness to 0)
            base.apply_translation([(width-1)/2, (height-1)/2, -base_plate_h/2])
            combined = trimesh.util.concatenate([surface_mesh, base])
        else:
            combined = surface_mesh

        # 6. Physical Scaling
        # Assuming 0.1mm per pixel as a base, then apply user scalePercent
        # If scalePercent is 100, a 1000px image becomes 100mm
        pixel_to_mm = 0.1 * (scale_percent / 100.0)
        combined.apply_scale(pixel_to_mm)

        # 7. Final Export
        output_dir = "/tmp/sand_art_output"
        os.makedirs(output_dir, exist_ok=True)
        
        temp_filename = f"sand_art_{uuid.uuid4().hex[:8]}.stl"
        temp_path = os.path.join(output_dir, temp_filename)
        
        combined.export(temp_path)
        return temp_path

    except Exception as e:
        print(f"STL Generation Error: {e}")
        return None