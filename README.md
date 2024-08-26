# Blender BSP Importer

This is a .bsp file importer which supports different id tech 3 games bsp formats. It also features md3 and tiki tan importers and exporters as also a WIP .map importer. Materials are approximated from the .shader files of the games. All files are also read from a virtual file system that can read pk3 files. Configuring the base path in the addons preferences is recommended for this.

Blender versions 2.93 to 4.2 are supported right now

**Please do not use this addon to copy or steal another creators work. Always ask for the creators permission.**

## Features:

 - [Import BSP files](https://github.com/SomaZ/Blender_BSP_Importer/wiki/Importing-BSP-files)
 - Bake lightmaps 
 - Edit lightmap coordinates
 - Bake lightgrid
 - Bake vertex colors
 - Edit texture coordinates
 - Edit vertex normals
 - Edit entities
 - Import MD3 files
 - Export MD3 files
 - Import Tiki tan files
 - Export Tiki tan files
 - Import legacy MAP files (no BP or V220 support for now)

## Supported Games (excerpt):

| Game | Patch edits |
| - | - |
| Quake 3 | :heavy_check_mark: |
| Star Trek Elite Force | :heavy_check_mark: |
| Star Trek Elite Force 2 | :x: |
| Star Wars Jedi Knight Jedi Outcast | :heavy_check_mark: |
| Star Wars Jedi Knight Jedi Academy | :heavy_check_mark: |
| Soldier of Fortune II | :heavy_check_mark: |
| American McGee’s Alice | :x: |
| Heavy Metal: F.A.K.K.2 | :x: |
| Xonotic | :heavy_check_mark: |
| Warsow | :heavy_check_mark: |
| Warfork | :heavy_check_mark: |

[More](https://github.com/SomaZ/Blender_BSP_Importer/wiki/Supported-Games)

## How to install:

 - Download the addon zip file
 - Open Blender
 - Go to 'Edit -> Preferences -> Add-ons'
 - Click the 'Install...' button on the top right and navigate to the zip you downloaded, then click 'Install Add-on'
 - Tick the checkbox next to 'Import-Export: Import id Tech 3 BSP' to enable the addon
 - Optionally add your base path and mod paths in the addons preferences

For more information consult the [Wiki](https://github.com/SomaZ/Blender_BSP_Importer/wiki/Setup)

## Attributions

- Virtual file system support by Alexander @cagelight Sago 
