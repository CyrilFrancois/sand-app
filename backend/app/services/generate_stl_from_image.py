import numpy as np
import trimesh
from PIL import Image
import io
import os
import uuid

def generate_stl_from_image(image_bytes, settings):
    try:
        # 1. Load the image as Grayscale (L)
        # image_bytes is the raw binary from the GPT response
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        
        # 2. Get Settings
        wall_h = float(settings.get('wallHeight', 3))
        thick = float(settings.get('wallThickness', 0.8))
        target_size = float(settings.get('targetSize', 150))

        # 3. Resize to target size (mm to pixels scale)
        # We'll treat 1px as a small unit and scale the final mesh
        img.thumbnail((500, 500)) 
        width, height = img.size
        
        # 4. Convert to Binary (Black lines = 1, White = 0)
        # Threshold at 128 (standard mid-grey)
        data = np.array(img)
        binary_mask = (data < 128).astype(np.uint8)

        # 5. Create the 3D Geometry
        # We create a base plate first
        base_plate = trimesh.creation.box(extents=(width, height, 1))
        base_plate.apply_translation([0, 0, -0.5]) # Shift so top is at Z=0

        # We create the "walls" by extruding the black pixels
        # For a simple robust version, we use a heightmap/voxel approach
        # or simply extrude the mask
        nodes = []
        for y in range(height):
            for x in range(width):
                if binary_mask[y, x] == 1:
                    # Create a small box for each black pixel
                    # (Optimized production code would use a mesh from contours)
                    pixel_box = trimesh.creation.box(extents=(1.1, 1.1, wall_h))
                    pixel_box.apply_translation([x - width/2, height/2 - y, wall_h/2])
                    nodes.append(pixel_box)

        # Combine all boxes + base plate
        if nodes:
            combined = trimesh.util.concatenate([base_plate] + nodes)
        else:
            combined = base_plate

        # 6. Scale to targetSize (mm)
        scale_factor = target_size / max(width, height)
        combined.apply_scale(scale_factor)

        # 7. Save to temp folder
        temp_filename = f"sand_art_{uuid.uuid4().hex}.stl"
        temp_path = os.path.join("/app/app/temp", temp_filename)
        combined.export(temp_path)
        
        return temp_path

    except Exception as e:
        print(f"STL Generation Error: {e}")
        return None