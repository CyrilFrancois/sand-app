from trimesh.creation import extrude_polygon
import shapely
import trimesh


def svg_to_stl(svg_string, output_path, wall_height, wall_thickness, base_plate):
    # TODO: parse actual SVG paths
    # placeholder geometry

    square = shapely.box(0, 0, 100, 100)
    mesh = extrude_polygon(square, wall_height)

    mesh.export(output_path)
