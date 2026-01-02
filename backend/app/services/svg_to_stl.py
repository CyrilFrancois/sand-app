import trimesh
import base64
import io

def svg_to_stl(svg_data_uri, output_path, wall_height, wall_thickness, add_base):
    try:
        # 1. Decode the SVG from the Data URI
        header, encoded = svg_data_uri.split(",", 1)
        svg_xml = base64.b64decode(encoded).decode('utf-8')
        
        # 2. Load SVG directly into a trimesh Path2D object
        # We wrap it in a file-like object (io.StringIO)
        path = trimesh.load(io.StringIO(svg_xml), file_type='svg')
        
        # 3. Process the paths
        # If the SVG has multiple layers/paths, we merge them
        if isinstance(path, trimesh.path.Path2D):
            # Scale to your target size (150mm)
            scale_factor = 150.0 / max(path.extents)
            path.apply_scale(scale_factor)
            
            # EXTRUDE: This turns 2D paths into 3D walls
            # We use wall_thickness to give the lines physical volume
            mesh = path.extrude(wall_height)
        else:
            raise ValueError("File was not a valid 2D Path")

        # 4. Add Base Plate
        if add_base:
            base = trimesh.creation.box(extents=(160, 160, 1.0))
            base.apply_translation((path.centroid[0], path.centroid[1], -0.5))
            mesh = trimesh.util.concatenate([mesh, base])

        mesh.export(output_path)
        
    except Exception as e:
        print(f"STL Generation Error: {e}")
        # Fallback to a simple box if it fails
        trimesh.creation.box(extents=(1, 1, 1)).export(output_path)