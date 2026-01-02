import numpy as np
import trimesh
from PIL import Image
import io
import os
import uuid

def generate_stl_from_image(image_bytes, settings):
    try:
        # 1. Load the image
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        
        # 2. Get Settings
        wall_h = float(settings.get('wallHeight', 3))
        target_size = float(settings.get('targetSize', 150))

        # 3. Resize for processing speed
        img.thumbnail((300, 300)) # Lowered slightly to speed up pixel-looping
        width, height = img.size
        
        # 4. Binary mask
        data = np.array(img)
        binary_mask = (data < 128).astype(np.uint8)

        # 5. Build Geometry
        base_plate = trimesh.creation.box(extents=(width, height, 1))
        base_plate.apply_translation([0, 0, -0.5]) 

        nodes = []
        for y in range(height):
            for x in range(width):
                if binary_mask[y, x] == 1:
                    pixel_box = trimesh.creation.box(extents=(1.1, 1.1, wall_h))
                    pixel_box.apply_translation([x - width/2, height/2 - y, wall_h/2])
                    nodes.append(pixel_box)

        if nodes:
            combined = trimesh.util.concatenate([base_plate] + nodes)
        else:
            combined = base_plate

        scale_factor = target_size / max(width, height)
        combined.apply_scale(scale_factor)

        # --- THE FIX STARTS HERE ---
        # Ensure the directory exists before exporting
        output_dir = "/tmp/sand_art_output" # Using /tmp is safer in Docker
        os.makedirs(output_dir, exist_ok=True)
        
        temp_filename = f"sand_art_{uuid.uuid4().hex}.stl"
        temp_path = os.path.join(output_dir, temp_filename)
        
        combined.export(temp_path)
        # --- THE FIX ENDS HERE ---
        
        return temp_path

    except Exception as e:
        print(f"STL Generation Error: {e}")
        return None