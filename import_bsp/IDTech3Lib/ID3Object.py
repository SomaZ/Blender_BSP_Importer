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

from math import floor, ceil, pi, sin, cos, radians


class ID3Object:

    def __init__(self, name="EmptyObject", mesh_name=None):
        self.name = name
        self.position = (0.0, 0.0, 0.0)
        self.rotation = (0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.mesh_name = mesh_name
        self.parent_object_name = ""
        self.custom_parameters = {}
        self.spawnflags = 0

    @classmethod
    def from_entity_dict(self, ent_dict, name="EmptyObject", mesh_name=None):
        new_object = self(name, mesh_name)
        for key in ent_dict:
            new_object.parse_entity_def(key, ent_dict[key])
        return new_object

    def set_angle(self, angle):
        self.rotation = (0.0, 0.0, radians(angle))

    def set_angles(self, angles):
        self.rotation = (radians(angles[2]),
                         radians(angles[0]),
                         radians(angles[1]))

    def set_scale(self, scale):
        self.scale = (scale, scale, scale)

    def set_scale_vec(self, scale_vec):
        self.scale = (scale_vec[0],
                      scale_vec[1],
                      scale_vec[2])

    def set_origin(self, origin):
        self.position = tuple(origin)

    def set_spawnflags(self, spawnflags):
        self.spawnflags = spawnflags

    def set_mesh_name(self, mesh_name):
        if not self.name == "worldspawn":
            self.mesh_name = mesh_name

    def set_name(self, target_name):
        self.name = target_name

    def parse_entity_def(self, key, value):
        key_loopup = {
            "origin": self.set_origin,
            "angle": self.set_angle,
            "angles": self.set_angles,
            "modelscale_vec": self.set_scale_vec,
            "modelscale": self.set_scale,
            "spawnflags": self.set_spawnflags,
            "model": self.set_mesh_name,
            "target_name": self.set_mesh_name
        }
        if key not in key_loopup:
            self.custom_parameters[key] = value
            return

        key_loopup[key](value)
