import bpy
import threading
import requests
from pathlib import Path
import os

from ...base_node import SN_ScriptingBaseNode
from ...templates.VariableReferenceNode import VariableReferenceNode

class SN_SKD_DownLoadFileProgress_any_Node(SN_ScriptingBaseNode, bpy.types.Node, VariableReferenceNode):
    bl_idname = "SN_SKD_DownLoadFileProgress_any_Node"
    bl_label = "Download File Progress Variable"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("File URL").subtype = "FILE_PATH"
        self.add_string_input("Save Path").subtype = "DIR_PATH"
        self.ref_ntree = self.node_tree

    def evaluate(self, context):
        var = self.get_var()
        if var is None:
            return

        self.code_import = """
                            import threading
                            import requests
                            from pathlib import Path
                            import os
                            import urllib.parse
                            """

        self.code_imperative = f"""
                                def download_file_any(url, save_dir):
                                    {var.data_path} = 0.0

                                    class DownloadThread(threading.Thread):
                                        def __init__(self, url, save_dir):
                                            super().__init__()
                                            self.url = url
                                            self.filename = os.path.basename(urllib.parse.unquote(url))
                                            self.save_path = Path(save_dir) / self.filename
                                            self.progress = 0
                                            self.completed = False
                                            self.error = None
                                            self.lock = threading.Lock()
                                            self.max_redirects = 10
                                            self.redirect_count = 0

                                        def follow_redirects(self, url):
                                            session = requests.Session()
                                            while self.redirect_count < self.max_redirects:
                                                try:
                                                    response = session.head(url, allow_redirects=False)
                                                    if response.status_code in (301, 302, 303, 307, 308):
                                                        url = response.headers['location']
                                                        if not url.startswith('http'):
                                                            # Handle relative redirects
                                                            url = urllib.parse.urljoin(response.url, url)
                                                        self.redirect_count += 1
                                                    else:
                                                        break
                                                except Exception as e:
                                                    raise Exception(f"Error following redirects: {{str(e)}}")
                                            return url

                                        def run(self):
                                            try:
                                                self.save_path.parent.mkdir(parents=True, exist_ok=True)
                                                
                                                # First, follow redirects to get the final URL
                                                final_url = self.follow_redirects(self.url)
                                                
                                                # Get the filename from the final URL
                                                parsed_url = urllib.parse.urlparse(final_url)
                                                self.filename = os.path.basename(urllib.parse.unquote(parsed_url.path))
                                                if not self.filename:  # If filename is empty, use a default
                                                    self.filename = "downloaded_file"
                                                
                                                self.save_path = Path(self.save_path.parent) / self.filename

                                                # Now download the file
                                                with requests.get(final_url, stream=True) as response:
                                                    response.raise_for_status()
                                                    total_size = int(response.headers.get('content-length', 0))
                                                    downloaded_size = 0

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

                                            except Exception as e:
                                                with self.lock:
                                                    self.error = f"Error: {{str(e)}}"
                                                if self.save_path.exists():
                                                    self.save_path.unlink(missing_ok=True)

                                    thread = DownloadThread(url, save_dir)
                                    thread.start()

                                    def update_progress():
                                        with thread.lock:
                                            if thread.error:
                                                print(f"Error: {{thread.error}}")
                                                return None
                                            if not thread.completed:
                                                {var.data_path} = thread.progress
                                                return 0.1
                                            {var.data_path} = 100
                                            return None

                                    bpy.app.timers.register(update_progress)
                                """

        self.code = f"""anydownloadprogress_{self.static_uid} = download_file_any({self.inputs[1].python_value}, {self.inputs[2].python_value})"""
        self.outputs[0].python_value = f"anydownloadprogress_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        self.draw_variable_reference(layout)
        if self.get_var() is None:
            layout.label(text="Variable not set!", icon="ERROR")