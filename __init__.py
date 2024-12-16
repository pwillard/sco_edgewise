bl_info = {
    "name": "SCO EdgeWise",
    "author": "BEAST_of_BURDEN",
    "version": (2, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > Item Tab > Edit Mode",
    "description": "Measure distances, edge lengths, and angles in edit mode",
    "category": "Object",
}

import bpy
from . import sco_edgewise 

def register():
    sco_edgewise.register()

def unregister():
    sco_edgewise.unregister()

if __name__ == "__main__":
    register()
