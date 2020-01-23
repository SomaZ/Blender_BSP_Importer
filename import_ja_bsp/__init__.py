# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Import id Tech 3 BSP",
    "author": "SomaZ",
	"version": (0, 8, 9),
    "description": "Importer for id Tech 3 BSP levels",
    "blender": (2, 81, 16),
    "location": "File > Import-Export",
	"warning": "",
    "category": "Import-Export"
}

#  Imports

#  Python
import imp

#  Blender
if "bpy" not in locals():
    import bpy
    
if "BspImport" in locals():
    imp.reload( BspImport )
else:
    from . import BspImport

# ------------------------------------------------------------------------
#    store properties in the user preferences
# ------------------------------------------------------------------------
class BspImportAddonPreferences(bpy.types.AddonPreferences):

    bl_idname = __name__

    base_path : bpy.props.StringProperty(
        name="basepath",
        description="Path to base folder",
        default="C:/Program Files (x86)/Steam/steamapps/common/Jedi Academy/GameData/base",
        maxlen=2048,
        )

    #shader_dir : bpy.props.StringProperty(
    #    name="shader dir",
    #    description="Shader directory name",
    #    default="shaders/",
    #    maxlen=2048,
    #    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "base_path")
        #layout.prop(self, "shader_dir")
	
classes = ( BspImport.Operator,
            BspImportAddonPreferences,
            BspImport.Q3_PT_MappingPanel,
            BspImport.Reload_shader,)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(BspImport.menu_func)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(BspImport.menu_func)
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()