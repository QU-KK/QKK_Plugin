import bpy
import os
import sys

from ... utils.registration import get_path, get_prefs, get_version_files, get_version_from_filename, get_version_from_blender, is_decal_folder_valid, is_library_trimsheet
from ... utils.system import get_folder_contents, makedir, open_folder, get_PIL_image_module_path
from ... utils.assets import get_ambiguous_libs, get_invalid_libs, get_corrupt_libs
from ... utils.library import get_short_library_path

from ... import bl_info
from ... import DECALmachineManager as DM

enc = sys.getdefaultencoding()

class GetSupport(bpy.types.Operator):
    bl_idname = "machin3.get_decalmachine_support"
    bl_label = "MACHIN3: Get DECALmachine Support"
    bl_description = "Generate Log Files and Instructions for a Support Request."
    bl_options = {'REGISTER'}

    def execute(self, context):
        logpath = makedir(os.path.join(get_path(), "logs"))
        resourcespath = makedir(os.path.join(get_path(), "resources"))
        assetspath = get_prefs().assetspath

        pillog = []

        if not os.path.exists(os.path.join(logpath, "pil.log")):
            pillog.append("'pil.log' not found!")

            try:
                import PIL
                pillog.append(f"PIL {PIL.__version__} imported successfully")
                pil = True

            except:
                pillog.append("PIL could not be imported")
                pil = False

            if pil:
                try:
                    from PIL import Image
                    pillog.append(f"PIL's Image module imported successful from '{get_PIL_image_module_path(Image)}'")

                except:
                    pillog.append("PIL's Image module could not be imported")

            with open(os.path.join(logpath, "pil.log"), "w") as f:
                f.writelines([l + "\n" for l in pillog])

        sysinfopath = os.path.join(logpath, "system_info.txt")
        bpy.ops.wm.sysinfo(filepath=sysinfopath)

        assets_dict = DM.get_assets_dict(force=True)

        self.extend_system_info(context, sysinfopath, assetspath, assets_dict)

        src = os.path.join(resourcespath, "readme.html")
        readmepath = os.path.join(logpath, "readme.html")

        with open(src, "r") as f:
            html = f.read()

        html = html.replace("VERSION", ".".join((str(v) for v in bl_info['version'])))

        folderurl = "file://" + logpath
        html = html.replace("FOLDER", f'<a href="{folderurl}">DECALmachine/logs</a>')

        with open(readmepath, "w") as f:
            f.write(html)

        readmeurl = "file://" + readmepath
        bpy.ops.wm.url_open(url=readmeurl)

        open_folder(logpath)

        return {'FINISHED'}

    def extend_system_info(self, context, sysinfopath, assetspath, assets_dict):
        if os.path.exists(sysinfopath):
            with open(sysinfopath, 'r+', encoding=enc) as f:
                lines = f.readlines()
                newlines = lines.copy()

                for line in lines:
                    if all(string in line for string in ['version:', 'branch:', 'hash:']):
                        idx = newlines.index(line)
                        newlines.pop(idx)
                        newlines.insert(idx, line.replace(', type:', f", revision: {bl_info['revision']}, type:"))

                    elif line.startswith('DECALmachine'):
                        idx = newlines.index(line)

                        new = []

                        filters = [ws for ws in bpy.data.workspaces if ws.use_filter_by_owner]

                        if filters:
                            new.append("")
                            new.append("Workspace Addon Filters")

                            for ws in filters:
                                new.append(f"  {'🚫'} Addon Filtering enabled on '{ws.name}' Workspace")

                        if new:
                            new.append("")

                        new.append(f"Assets Location: {assetspath}")
                        new.append(f"        Version: {get_version_from_blender()}")

                        new.append("\n  ✔  Registered Assets =============")

                        registered = False

                        if atlases := assets_dict['ATLASES']:
                            new.append("\n    Atlases")

                            for path in atlases:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                            registered = True

                        if decals := assets_dict['DECALS']:
                            new.append("\n    Decals")

                            for path in decals:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                            registered = True

                        if trims := assets_dict['TRIMS']:
                            new.append("\n    Trims")

                            for path in trims:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                            registered = True

                        if not registered:
                            new.append("\n    None")

                        new.append("\n  🐵 Updateable/Fixable Assets  ====")

                        updateable = False

                        if legacy := assets_dict['LEGACY']:
                            new.append("\n    Legacy")

                            for path in legacy:
                                shortpath = get_short_library_path(path, assets_root=False)
                                versions = get_version_files(path)

                                new.append(f"    📁 {shortpath} - {get_version_from_filename(versions[0])}")

                                self.show_folder_contents(path, new, list_folders=True, list_files=False, decal_folder_check=True)

                            updateable = True

                        if ambiguous := get_ambiguous_libs():
                            new.append("\n    Ambiguous")

                            for path in ambiguous:
                                shortpath = get_short_library_path(path, assets_root=False)
                                versions = get_version_files(path)

                                new.append(f"    📁 {shortpath} - {', '.join(sorted([get_version_from_filename(v) for v in versions]))}")

                                self.show_folder_contents(path, new, list_folders=True, list_files=True, decal_folder_check=True)

                            updateable = True

                        if not updateable:
                            new.append("\n    None")

                        new.append("\n  ❌ Deferred Assets  ==============")

                        deferred = False

                        if future := assets_dict['FUTURE']:
                            new.append("\n    Next-Gen")

                            for path in future:
                                shortpath = get_short_library_path(path, assets_root=False)
                                versions = get_version_files(path)

                                new.append(f"    📁 {shortpath} - {get_version_from_filename(versions[0])}")

                                self.show_folder_contents(path, new, list_folders=True, list_files=False, decal_folder_check=True)

                            deferred = True

                        if obsolete := assets_dict['OBSOLETE']:
                            new.append("\n    Obsolete")

                            for path in obsolete:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                                self.show_folder_contents(path, new, list_folders=True, list_files=False, decal_folder_check=True)

                            deferred = True

                        if invalid := get_invalid_libs():
                            new.append("\n    Invalid")

                            for path in invalid:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                                self.show_folder_contents(path, new, list_folders=True, list_files=True, decal_folder_check=True)

                            deferred = True

                        if corrupt := get_corrupt_libs():
                            new.append("\n    Corrupt")

                            for path in corrupt:

                                trimspath = os.path.join(assetspath, 'Trims')
                                is_misplaced = trimspath in path and not is_library_trimsheet(path)

                                shortpath = get_short_library_path(path, assets_root=False)
                                versions = get_version_files(path)

                                new.append(f"    📁 {shortpath}{' ⚠️  Non-Trimsheet Library in Trims location!' if is_misplaced else ''} - {', '.join(sorted([get_version_from_filename(v) for v in versions]))}")

                                self.show_folder_contents(path, new, list_folders=True, list_files=True, decal_folder_check=True)

                            deferred = True

                        if clutter := assets_dict['CLUTTER']:
                            new.append("\n    Clutter")

                            for path in clutter:
                                is_dir = os.path.isdir(path)
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    {'📁' if is_dir else '📄'} {shortpath}")

                            deferred = True

                        if decluttered := assets_dict['DECLUTTERED']:
                            new.append("\n    Decluttered")

                            for path in decluttered:
                                is_dir = os.path.isdir(path)
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    {'📁' if is_dir else '📄'} {shortpath}")

                            deferred = True

                        if collided := assets_dict['COLLIDED']:
                            new.append("\n    Collided")

                            for path in collided:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                            deferred = True

                        if quarantined := assets_dict['QUARANTINED']:
                            new.append("\n    Quarantined")

                            for path in quarantined:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                                self.show_log_file(path, new, logtype='QUARANTINED')

                            deferred = True

                        if skipped := assets_dict['SKIPPED']:
                            new.append("\n    Skipped")

                            for path in skipped:
                                shortpath = get_short_library_path(path, assets_root=False)

                                new.append(f"    📁 {shortpath}")

                                self.show_log_file(path, new, logtype='SKIPPED')

                            deferred = True

                        if not deferred:
                            new.append("\n    None")

                        new.extend(['',
                                    '🖌 Color Management ==============',
                                    '',
                                    f"  View Transform: {context.scene.view_settings.view_transform}",
                                    f"            Look: {context.scene.view_settings.look}",
                                    f"       Sequencer: {context.scene.sequencer_colorspace_settings.name}",
                                    ''])

                        for n in new:
                            idx += 1
                            newlines.insert(idx, f"  {n}\n")

                f.seek(0)
                f.writelines(newlines)

    def show_folder_contents(self, path, new, list_folders=True, list_files=True, decal_folder_check=True):
        folders, files = get_folder_contents(path)

        if list_folders:
            if folders:
                for fldr in folders:
                    if decal_folder_check:
                        new.append(f"      📁 {fldr} {'✔' if is_decal_folder_valid(os.path.join(path, fldr)) else '❌'}")
                    else:
                        new.append(f"      📁 {fldr}")

        if list_files:
            if files:
                for fl in files:
                    new.append(f"      📄 {fl}")

    def show_log_file(self, path, new, logtype='QUARANTINED'):
        if os.path.exists(logpath := os.path.join(path, 'log.txt')):
            with open(logpath) as f:
                lines = [line[:-1] for line in f.readlines()]

            if logtype == 'SKIPPED':
                new[-1] += (f" ⚠️  {'SOME' if 'SOME Decals' in lines[0] else 'ALL'} Decals were skipped")

            elif logtype == 'QUARANTINED':

                q_reasons = []

                for line in lines[2:]:
                    if line.startswith('📄'):
                        continue
                    elif line.startswith('📁'):
                        continue

                    if 'obsolete' in line:
                        q_reasons.append('OBSOLETE')

                    elif 'not a valid' in line or 'invalid' in line:
                        q_reasons.append('INVALID')

                    elif '.png image files' in line:
                        q_reasons.append('PNG')

                    elif 'non-png image files' in line:
                        q_reasons.append('IMAGE')

                    elif 'corrupt' in line:
                        q_reasons.append('CORRUPT')

                    elif 'ambiguous' in line:
                        q_reasons.append('AMBIGUOUS')

                if len(lines) >= 3 and "It's in the Trims location, but" in lines[2]:
                    new[-1] += f" ⚠️  {', '.join(q_reasons)} - Non-Trimsheet Library in Trims location!"

                else:
                    new[-1] += f" ⚠️  {', '.join(q_reasons)}"

            for idx, line in enumerate(lines):

                if '@machin3.io' in line:
                    new.pop(-1)
                    continue

                elif line.startswith('📄'):
                    if 'AMBIGUOUS' in q_reasons:
                        filename, _ = line.split(' - version ')
                        new.append(f"       {filename}")

                    else:
                        new.append(f"       {line}")

                elif line.startswith('📁'):
                    repl = line.replace('- invalid Decal folder', '❌').replace('- valid Decal folder', '✔')
                    new.append(f"       {repl}")

class CoatInfo(bpy.types.Operator):
    bl_idname = "machin3.coat_info"
    bl_label = "Please Note"
    bl_description = "Coat Information"
    bl_options = {'INTERNAL'}

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        column.label(text="This setting affects all decals in the blend file globally!")
        column.label(text="This is because DECALmachine attempts to re-use not only decal materials,")
        column.label(text="but also the node trees used by the decal node groups in those materials.")
        column.label(text="")
        column.label(text="Re-using materials and node trees like that is - and always was - wise in terms of")
        column.label(text="performance and file size.")
        column.label(text="However, in case you want to have some decals under the coat, and others over,")
        column.label(text="you will - for now - have to set it up manually.")
        column.label(text="")
        column.label(text="Study the decal material and its decal group's node tree to find out how the effect works.")
        column.label(text="Get in touch with decal@machin3.io if you need assistance.")

    def invoke(self, context, invoke):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):
        return {'FINISHED'}
