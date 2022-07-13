from numpy import array, deg2rad


class ID3Object:

    def __init__(self, name="EmptyObject", mesh_name=None):
        self.name = name
        self.position = array((0.0, 0.0, 0.0))
        self.rotation = array((0.0, 0.0, 0.0))
        self.scale = array((1.0, 1.0, 1.0))
        self.mesh_name = mesh_name
        self.model2 = ""
        self.parent_object_name = ""
        self.custom_parameters = {}
        self.spawnflags = 0
        self.zoffset = 0

    @classmethod
    def from_entity_dict(self, ent_dict, name="EmptyObject", mesh_name=None):
        new_object = self(name, mesh_name)
        for key in ent_dict:
            new_object.parse_entity_def(key, ent_dict[key])
        return new_object

    def set_angle(self, angle):
        self.rotation = array((0.0, 0.0, deg2rad(angle)))

    def set_angles(self, angles):
        self.rotation = array((deg2rad(angles[2]),
                               deg2rad(angles[0]),
                               deg2rad(angles[1])))

    def set_scale(self, scale):
        self.scale = array((scale, scale, scale))

    def set_scale_vec(self, scale_vec):
        self.scale = array((scale_vec[0],
                            scale_vec[1],
                            scale_vec[2]))

    def set_origin(self, origin):
        self.position = array(origin)

    def set_spawnflags(self, spawnflags):
        self.spawnflags = int(spawnflags)

    def set_mesh_name(self, mesh_name):
        if not self.name == "worldspawn":
            self.mesh_name = str(mesh_name)

    def set_model2(self, mesh_name):
        self.set_model2 = str(mesh_name)

    def set_name(self, target_name):
        self.name = str(target_name)

    def set_zoffset(self, zoffset):
        self.zoffset = int(zoffset)

    def parse_entity_def(self, key, value):
        key_loopup = {
            "origin": self.set_origin,
            "angle": self.set_angle,
            "angles": self.set_angles,
            "modelscale_vec": self.set_scale_vec,
            "modelscale": self.set_scale,
            "spawnflags": self.set_spawnflags,
            "model": self.set_mesh_name,
            "model2": self.set_model2,
            "target_name": self.set_name,
            "zoffset": self.set_zoffset,
        }
        if key not in key_loopup:
            self.custom_parameters[key] = value
            return

        key_loopup[key](value)
