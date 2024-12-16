# Blender Addon - SCO EdgeWise
# Version: 2.0.0
# Author: BEAST_of_BURDEN (scottb613@yahoo.com)

# This script is licensed under the GNU General Public License GPLv3.
# See the LICENSE file for more details.

import bpy
import bmesh
from math import degrees


class TapeMeasureProperties(bpy.types.PropertyGroup):
    result: bpy.props.StringProperty(name="Measurement Result", default="")
    last_mode: bpy.props.StringProperty(name="Last Selection Mode", default="NONE")  # To track mode changes


def convert_distance(distance, unit_settings):
    if unit_settings.system == 'IMPERIAL':
        return distance * 3.28084  # Convert meters to feet
    return distance  # Metric is the default in meters


def get_unit_suffix(unit_settings):
    if unit_settings.system == 'IMPERIAL':
        return 'ft'
    return 'm'


class TapeMeasureOperator(bpy.types.Operator):
    """Measure selected points or edges"""
    bl_idname = "mesh.tape_measure"
    bl_label = "Measure"
    bl_options = {'REGISTER', 'UNDO'}

    def is_contiguous(self, edges):
        """Check if edges form a contiguous group"""
        visited = set()
        stack = [edges[0]]  # Start with the first edge

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)

            # Add all connected edges to the stack
            connected_edges = [
                e for e in edges if e not in visited and any(v in current.verts for v in e.verts)
            ]
            stack.extend(connected_edges)

        # Contiguous if we visited all edges
        return len(visited) == len(edges)

    def get_selected_vertices(self, context):
        """Get all selected vertices in world space from selected objects"""
        selected_verts = []
        for obj in context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()

                # Collect selected vertices transformed to world space
                selected_verts += [obj.matrix_world @ v.co for v in bm.verts if v.select]
        return selected_verts

    def execute(self, context):
        props = context.scene.tape_measure_props
        unit_settings = context.scene.unit_settings

        # Detect selection mode
        select_mode = bpy.context.tool_settings.mesh_select_mode
        current_mode = "VERTEX" if select_mode[0] else "EDGE" if select_mode[1] else "NONE"

        # Detect mode changes and reset result if necessary
        if props.last_mode != current_mode:
            props.last_mode = current_mode
            props.result = ""

        result = ""

        if current_mode == "VERTEX":  # Vertex selection logic
            selected_verts = self.get_selected_vertices(context)
            if len(selected_verts) == 2:  # Measure distance between two points
                v1, v2 = selected_verts
                distance = (v1 - v2).length
                distance = convert_distance(distance, unit_settings)
                unit = get_unit_suffix(unit_settings)
                result = f"{distance:.2f} {unit}"
            elif len(selected_verts) != 2:  # Invalid number of vertices
                self.report({'ERROR'}, "Invalid selection: Select exactly two vertices")
                return {'CANCELLED'}

        elif current_mode == "EDGE":  # Edge selection logic
            obj = context.object
            if obj is None or obj.type != 'MESH':
                self.report({'ERROR'}, "Active object is not a mesh")
                return {'CANCELLED'}

            bm = bmesh.from_edit_mesh(obj.data)
            selected_edges = [e for e in bm.edges if e.select]

            if len(selected_edges) == 1:  # Single edge
                edge = selected_edges[0]
                distance = edge.calc_length()
                distance = convert_distance(distance, unit_settings)
                unit = get_unit_suffix(unit_settings)
                result = f"{distance:.2f} {unit}"
            elif len(selected_edges) > 1 and self.is_contiguous(selected_edges):  # Contiguous group of edges
                total_length = sum(e.calc_length() for e in selected_edges)
                total_length = convert_distance(total_length, unit_settings)
                unit = get_unit_suffix(unit_settings)
                result = f"{total_length:.2f} {unit}"
            elif len(selected_edges) > 1:  # Non-contiguous edges
                self.report({'ERROR'}, "Invalid selection: Edges must form a contiguous group")
                return {'CANCELLED'}
            else:  # No valid edges selected
                self.report({'ERROR'}, "Invalid selection: Select a single edge or contiguous edge group")
                return {'CANCELLED'}

        else:  # Invalid mode
            self.report({'ERROR'}, "Invalid selection mode: Use Vertex or Edge mode")
            return {'CANCELLED'}

        # Update the result field
        props.result = result
        return {'FINISHED'}


class AngleMeasureOperator(bpy.types.Operator):
    """Measure angles between two selected edges"""
    bl_idname = "mesh.angle_measure"
    bl_label = "Measure Angles"
    bl_options = {'REGISTER', 'UNDO'}

    def calculate_angle(self, edge1, edge2):
        """Calculate the inside and outside angles between two edges"""
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
            self.report({'ERROR'}, "Invalid selection: Select exactly two edges")
            return {'CANCELLED'}

        edge1, edge2 = selected_edges
        angle_in, angle_out = self.calculate_angle(edge1, edge2)
        result = f"{angle_in:.2f}° | {angle_out:.2f}°"

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
            self.report({'ERROR'}, "Invalid selection: Select exactly one vertex")
            return {'CANCELLED'}

        selected_vert = selected_verts[0]
        axis_index = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        distance = selected_vert[axis_index] - cursor_location[axis_index]
        distance = convert_distance(abs(distance), unit_settings)
        unit = get_unit_suffix(unit_settings)

        props.result = f"{self.axis}: {distance:.2f} {unit}"
        return {'FINISHED'}


class TapeMeasurePanel(bpy.types.Panel):
    """EdgeWise Panel"""
    bl_label = "EdgeWise"
    bl_idname = "VIEW3D_PT_tape_measure"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 1100

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
        layout.separator()  # Adds blank line
        layout.operator("mesh.tape_measure", text="Measure Edges/Vertices")
        layout.operator("mesh.angle_measure", text="Measure Edge Angles")  # New button

        # Add spacing and new feature
        layout.separator(factor=1.0)
        layout.label(text="Vertex Distance from 3D Cursor:")
        row = layout.row()
        row.operator("mesh.distance_from_cursor", text="X").axis = 'X'
        row.operator("mesh.distance_from_cursor", text="Y").axis = 'Y'
        row.operator("mesh.distance_from_cursor", text="Z").axis = 'Z'


def clear_result_on_edit_mode(scene):
    if bpy.context.mode == 'EDIT_MESH':
        scene.tape_measure_props.result = ""
        scene.tape_measure_props.last_mode = "NONE"


def register():
    bpy.utils.register_class(TapeMeasureProperties)
    bpy.utils.register_class(TapeMeasureOperator)
    bpy.utils.register_class(AngleMeasureOperator)
    bpy.utils.register_class(DistanceFromCursorOperator)
    bpy.utils.register_class(TapeMeasurePanel)
    bpy.types.Scene.tape_measure_props = bpy.props.PointerProperty(type=TapeMeasureProperties)

    bpy.app.handlers.depsgraph_update_post.append(clear_result_on_edit_mode)


def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(clear_result_on_edit_mode)
    del bpy.types.Scene.tape_measure_props
    bpy.utils.unregister_class(TapeMeasureProperties)
    bpy.utils.unregister_class(TapeMeasureOperator)
    bpy.utils.unregister_class(AngleMeasureOperator)
    bpy.utils.unregister_class(DistanceFromCursorOperator)
    bpy.utils.unregister_class(TapeMeasurePanel)


if __name__ == "__main__":
    register()
