# Blender Addon: SCO EdgeWise
# Version 2.0.6
# Author: BEAST_of_BURDEN (sun503@yahoo.com)

# Support Page: https://github.com/pwillard/sco_edgewise/discussions

# This script is licensed under the GNU General Public License v3.
# See the LICENSE file for more details.

import bpy
import bmesh
from math import degrees, floor, log10

LENGTH_UNITS = {
    'KILOMETERS': (0.001, "km"),
    'METERS': (1.0, "m"),
    'CENTIMETERS': (100.0, "cm"),
    'MILLIMETERS': (1000.0, "mm"),
    'MICROMETERS': (1000000.0, "um"),
    'MILES': (0.000621371, "mi"),
    'FEET': (3.28084, "ft"),
    'INCHES': (39.3701, "in"),
    'THOU': (39370.1, "thou"),
}

class TapeMeasureProperties(bpy.types.PropertyGroup):
    result: bpy.props.StringProperty(name="Measurement Result", default="")
    last_mode: bpy.props.StringProperty(name="Last Selection Mode", default="NONE")

def convert_distance(distance, unit_settings):
    # Adjust for global unit scale
    adjusted_distance = distance * unit_settings.scale_length

    if unit_settings.system == 'NONE':
        return adjusted_distance, "units"

    if unit_settings.length_unit == 'ADAPTIVE':
        if unit_settings.system == 'IMPERIAL':
            return adjusted_distance * LENGTH_UNITS['FEET'][0], "ft"
        return adjusted_distance, "m"

    multiplier, suffix = LENGTH_UNITS.get(unit_settings.length_unit, (1.0, "units"))
    return adjusted_distance * multiplier, suffix

def format_distance(value, unit):
    if value == 0:
        return f"0.00 {unit}"

    decimals = max(2, min(8, 2 - floor(log10(abs(value)))))
    if decimals == 2:
        return f"{value:.2f} {unit}"

    formatted = f"{value:.{decimals}f}".rstrip('0').rstrip('.')
    return f"{formatted} {unit}"

class TapeMeasureOperator(bpy.types.Operator):
    """Measure selected points or edges"""
    bl_idname = "mesh.tape_measure"
    bl_label = "Measure"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None and context.object.type == 'MESH' and context.mode == 'EDIT_MESH')

    def is_contiguous(self, edges):
        """Check if edges form a contiguous group"""
        visited = set()
        stack = [edges[0]]

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)

            connected_edges = [
                e for e in edges if e not in visited and any(v in current.verts for v in e.verts)
            ]
            stack.extend(connected_edges)

        return len(visited) == len(edges)

    def get_selected_vertices(self, context):
        """Get all selected vertices in world space from selected objects"""
        selected_verts = []
        for obj in context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                selected_verts += [(obj.matrix_world @ v.co) for v in bm.verts if v.select]
        return selected_verts

    def execute(self, context):
        props = context.scene.tape_measure_props
        unit_settings = context.scene.unit_settings

        select_mode = context.tool_settings.mesh_select_mode
        current_mode = "VERTEX" if select_mode[0] else "EDGE" if select_mode[1] else "NONE"

        if props.last_mode != current_mode:
            props.last_mode = current_mode
            props.result = ""

        result = ""

        if current_mode == "VERTEX":
            selected_verts = self.get_selected_vertices(context)
            if len(selected_verts) == 2:
                v1, v2 = selected_verts
                distance = (v1 - v2).length
                converted_distance, unit = convert_distance(distance, unit_settings)
                result = format_distance(converted_distance, unit)
            else:
                self.report({'ERROR'}, "Select exactly two vertices")
                return {'CANCELLED'}

        elif current_mode == "EDGE":
            obj = context.object
            if obj is None or obj.type != 'MESH':
                self.report({'ERROR'}, "Active object is not a mesh")
                return {'CANCELLED'}

            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            selected_edges = [e for e in bm.edges if e.select]

            if len(selected_edges) == 1:
                edge = selected_edges[0]
                v1, v2 = edge.verts[0].co, edge.verts[1].co
                world_v1 = obj.matrix_world @ v1
                world_v2 = obj.matrix_world @ v2
                distance = (world_v1 - world_v2).length
                converted_distance, unit = convert_distance(distance, unit_settings)
                result = format_distance(converted_distance, unit)
            elif len(selected_edges) > 1 and self.is_contiguous(selected_edges):
                total_length = 0
                for edge in selected_edges:
                    v1, v2 = edge.verts[0].co, edge.verts[1].co
                    world_v1 = obj.matrix_world @ v1
                    world_v2 = obj.matrix_world @ v2
                    total_length += (world_v1 - world_v2).length
                converted_distance, unit = convert_distance(total_length, unit_settings)
                result = format_distance(converted_distance, unit)
            else:
                self.report({'ERROR'}, "Select a single edge or contiguous edge group")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "Use Vertex or Edge mode")
            return {'CANCELLED'}

        props.result = result
        return {'FINISHED'}

class AngleMeasureOperator(bpy.types.Operator):
    """Measure angles between two selected edges"""
    bl_idname = "mesh.angle_measure"
    bl_label = "Measure Angles"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None and context.object.type == 'MESH' and context.mode == 'EDIT_MESH')

    def calculate_angle(self, edge1, edge2):
        vec1 = edge1.verts[1].co - edge1.verts[0].co
        vec2 = edge2.verts[1].co - edge2.verts[0].co
        angle = vec1.angle(vec2)
        angle_in = degrees(angle)
        angle_out = 360 - angle_in
        return angle_in, angle_out

    def execute(self, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object is not a mesh")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        selected_edges = [e for e in bm.edges if e.select]

        if len(selected_edges) != 2:
            self.report({'ERROR'}, "Select exactly two edges")
            return {'CANCELLED'}

        edge1, edge2 = selected_edges
        angle_in, angle_out = self.calculate_angle(edge1, edge2)
        result = f"{angle_in:.2f} deg | {angle_out:.2f} deg"

        context.scene.tape_measure_props.result = result
        return {'FINISHED'}

class DistanceFromCursorOperator(bpy.types.Operator):
    """Calculate distance from 3D Cursor along a specific axis"""
    bl_idname = "mesh.distance_from_cursor"
    bl_label = "Distance from Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ('X', "X", "Distance along X-axis"),
            ('Y', "Y", "Distance along Y-axis"),
            ('Z', "Z", "Distance along Z-axis")
        ],
        default='X'
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        if context.mode != 'EDIT_MESH':
            return False
        for obj in context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                if sum(1 for v in bm.verts if v.select) == 1:
                    return True
        return False

    def execute(self, context):
        props = context.scene.tape_measure_props
        unit_settings = context.scene.unit_settings
        cursor_location = context.scene.cursor.location

        selected_verts = []
        for obj in context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                selected_verts += [obj.matrix_world @ v.co for v in bm.verts if v.select]

        if len(selected_verts) != 1:
            self.report({'ERROR'}, "Select exactly one vertex")
            return {'CANCELLED'}

        selected_vert = selected_verts[0]
        axis_index = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        distance = selected_vert[axis_index] - cursor_location[axis_index]
        converted_distance, unit = convert_distance(abs(distance), unit_settings)
        props.result = format_distance(converted_distance, unit)
        return {'FINISHED'}

class TapeMeasurePanel(bpy.types.Panel):
    """EdgeWise Panel"""
    bl_label = "SCO EdgeWise"
    bl_idname = "VIEW3D_PT_tape_measure"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        props = context.scene.tape_measure_props

        layout.prop(props, "result", text="Result")
        layout.separator()
        layout.operator("mesh.tape_measure", text="Measure Edges/Vertices")
        layout.operator("mesh.angle_measure", text="Measure Edge Angles")
        layout.separator(factor=1.0)
        layout.label(text="Vertex Distance from 3D Cursor:")
        row = layout.row()
        row.operator("mesh.distance_from_cursor", text="X").axis = 'X'
        row.operator("mesh.distance_from_cursor", text="Y").axis = 'Y'
        row.operator("mesh.distance_from_cursor", text="Z").axis = 'Z'

CLASSES = (
    TapeMeasureProperties,
    TapeMeasureOperator,
    AngleMeasureOperator,
    DistanceFromCursorOperator,
    TapeMeasurePanel,
)

# Register and Unregister Functions
def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.tape_measure_props = bpy.props.PointerProperty(type=TapeMeasureProperties)

def unregister():
    if hasattr(bpy.types.Scene, "tape_measure_props"):
        del bpy.types.Scene.tape_measure_props
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
