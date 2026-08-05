import bpy
import threading
import requests
from pathlib import Path
import os
import zipfile

from ...base_node import SN_ScriptingBaseNode
from ...templates.PropertyReferenceNode import PropertyReferenceNode

class SN_SKD_DownLoadFileProgressNodeProp(SN_ScriptingBaseNode, bpy.types.Node, PropertyReferenceNode):
    bl_idname = "SN_SKD_DownLoadFileProgressNodeProp"
    bl_label = "Download Zip File Progress Property"
    bl_width_default = 240
    node_color = "PROGRAM"


    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Zip File Path").subtype = "FILE_PATH"
        self.add_string_input("Save Path").subtype = "DIR_PATH"
        self.add_boolean_input("Unpack")
        self.ref_ntree = self.node_tree

    def evaluate(self, context):
        prop_src = self.get_prop_source()

        # Check if the property source and property name exist
        if prop_src is None or self.prop_name not in prop_src.properties:
            return

        prop = prop_src.properties[self.prop_name]

        # Check if the property has the required attribute
        if not hasattr(prop, "python_name"):
            return

        if prop_src is None:
            return
        

        self.code_import = """
                            import threading
                            import requests
                            from pathlib import Path
                            import os
                            import zipfile
                            """

        self.code_imperative = f"""
                                def download_fileProp(url, save_dir, unpacker):
                                    
                                    bpy.context.scene.{prop.python_name} = 0.0

                                    class DownloadThread(threading.Thread):
                                        def __init__(self, url, save_dir):
                                            super().__init__()
                                            self.url = url
                                            self.filename = os.path.basename(url)
                                            self.save_path = Path(save_dir) / self.filename
                                            self.progress = 0
                                            self.completed = False
                                            self.error = None
                                            self.lock = threading.Lock()

                                        def run(self):
                                            try:
                                                self.save_path.parent.mkdir(parents=True, exist_ok=True)
                                                with requests.get(self.url, stream=True, allow_redirects=True) as response:
                                                    response.raise_for_status()
                                                    final_url = response.url
                                                    self.filename = os.path.basename(final_url)
                                                    self.save_path = Path(self.save_path.parent) / self.filename
                                                    total_size = int(response.headers.get('content-length', 0))
                                                    downloaded_size = 0

                                                    # Downloading the file
                                                    with open(self.save_path, 'wb') as file:
                                                        for chunk in response.iter_content(chunk_size=8192):
                                                            if chunk:
                                                                file.write(chunk)
                                                                downloaded_size += len(chunk)
                                                                if total_size:
                                                                    with self.lock:
                                                                        self.progress = (downloaded_size / total_size) * 100
                                                
                                                with self.lock:
                                                    self.completed = True

                                                # Unpacking the zip file
                                                if unpacker:
                                                    if self.save_path.suffix == ".zip":
                                                        with zipfile.ZipFile(self.save_path, 'r') as zip_ref:
                                                            zip_ref.extractall(save_dir)
                                                
                                                    # Removing the zip file
                                                    if self.save_path.exists():
                                                        self.save_path.unlink()

                                            except Exception as e:
                                                with self.lock:
                                                    self.error = f"Error: {{str(e)}}"
                                                if self.save_path.exists():
                                                    self.save_path.unlink(missing_ok=True)

                                    thread = DownloadThread(url, save_dir)
                                    thread.start()

                                    def update_progress():

                                        with thread.lock:
                                            if thread.error:r
                                                print(f"Error: {{thread.error}}")
                                                return None
                                            if not thread.completed:
                                                bpy.context.scene.{prop.python_name} = thread.progress
                                                return 0.1
                                            bpy.context.scene.{prop.python_name} = 100
                    
                                            return None

                                    bpy.app.timers.register(update_progress)
                                """

        self.code = f"""zipdownloadprogresspprop_{self.static_uid} = download_fileProp({self.inputs[1].python_value}, {self.inputs[2].python_value}, {self.inputs[3].python_value})"""
        self.outputs[0].python_value = f"zipdownloadprogresspprop_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        self.draw_reference_selection(layout)
        prop_src = self.get_prop_source()
        if self.prop_name and prop_src and self.prop_name in prop_src.properties:
            if prop_src.properties[self.prop_name].property_type == "Group":
                self.draw_warning(layout, "Can't return Group properties!")

        if self.prop_name is None:
            layout.label(text="Property not set!", icon="ERROR")
