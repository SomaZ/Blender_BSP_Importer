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

import os
import re
import zipfile


class Q3VFS:

    class LooseFileRetriever:
        def __init__(self, path):
            self.path = path

        def get(self):
            fh = open(self.path, 'rb')
            data = bytearray(fh.read())
            fh.close()
            return data

    class PK3FileRetriever:
        def __init__(self, pk3, path):
            self.pk3 = pk3
            self.path = path

        def get(self):
            return self.pk3.read(self.path)

    def __init__(self):
        self.basepaths = []
        self.index = {}
        pass

    # add in order of preference, higher -> lower
    def add_base(self, path):
        if not os.path.isdir(path):
            raise Exception(
                'base path "{}" does not seem to exist'.format(path))
        self.basepaths.append(path)

    def build_index(self):
        for base in reversed(self.basepaths):
            for pk3_file in sorted(
                    [f for f in os.listdir(base) if f.endswith('.pk3')]):
                pk3h = zipfile.ZipFile(os.path.join(base, pk3_file), mode='r')
                for pk3f in [f for f in pk3h.infolist() if not f.is_dir()]:
                    self.index[pk3f.filename] = self.PK3FileRetriever(
                        pk3h, pk3f)
            for root, dirs, files in os.walk(base):
                for f in files:
                    abspath = os.path.join(root, f)
                    relpath = str(abspath[len(base):]).replace("\\", "/")
                    self.index[relpath] = self.LooseFileRetriever(abspath)

    def get(self, path):
        if path in self.index:
            return self.index[path].get()
        else:
            try:
                fh = open(path, 'rb')
                data = bytearray(fh.read())
                fh.close()
                return data
            except Exception:
                return None

    def search(self, reg):
        searcher = re.compile(reg)
        return [k for k in self.index if searcher.search(k)]