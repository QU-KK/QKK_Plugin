"""Send a bake to 3DCoat, Mari, and Substance Designer.

Painter, Marmoset, and Photoshop stay in ``external_handoff``. These three are
the editing apps: 3DCoat through its AppLink exchange folder, Mari through a
Python script the application runs, and Designer through a small plugin that
imports into the open package or creates one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from . import external_handoff


_COAT_IMPORT_COMMANDS = {
    "MATERIAL_ALBEDO": "$LOADTEX",
    "NORMAL": "$LOADLOPOLYTANG",
    "MATERIAL_NORMAL": "$LOADLOPOLYTANG",
    "WORLD_NORMAL": "$ImportOSNormal",
    "AO": "$ExternalAO",
    "CURVATURE": "$ExternalCavity",
    "PRINCIPAL_CURVATURE": "$ExternalCavity",
    "HEIGHT": "$LOAD_LAYER_DISP",
    "MATERIAL_ROUGHNESS": "$LOADROUGHNESS",
    "MATERIAL_METALNESS": "$LOADMETAL",
    "MATERIAL_EMISSION": "$LOADEMISSIVE",
    "MATERIAL_SPECULAR": "$LOADSPECCOL",
}

DESIGNER_PLUGIN_VERSION = 1
DESIGNER_LAUNCH_POLL_SECONDS = 0.5
DESIGNER_RUNNING_TIMEOUT_SECONDS = 12.0
DESIGNER_COLD_TIMEOUT_SECONDS = 180.0

_DESIGNER_PLUGIN = '''
import json
import os
import traceback
from pathlib import Path

REQUEST_DIR = Path(__FYR_REQUEST_DIR__)
REQUEST = REQUEST_DIR / "designer_request.json"
RESULT = REQUEST_DIR / "designer_result.json"
_TIMER = None
_BUSY = False


def _qt():
    try:
        from PySide6 import QtCore
    except ImportError:
        from PySide2 import QtCore
    return QtCore


def _write_result(ok, message):
    try:
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(
            json.dumps({"ok": bool(ok), "message": str(message)}),
            encoding="utf-8",
        )
    except Exception:
        print("[Fyr Baker] could not write the Designer result")


def _identifier(label):
    cleaned = []
    for character in str(label or ""):
        if character.isalnum() or character in "_.-":
            cleaned.append(character)
        elif character.isspace():
            cleaned.append("_")
    text = "".join(cleaned).strip("_.")
    return text or "Bake"


def _norm(path):
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        return os.path.normcase(os.path.abspath(text))
    except Exception:
        return text.replace("\\\\", "/").lower()


def _existing_paths(package):
    found = {}
    getter = getattr(package, "getChildrenResources", None)
    if not callable(getter):
        getter = getattr(package, "getChildren", None)
    children = []
    if callable(getter):
        try:
            children = list(getter(True) or ())
        except TypeError:
            try:
                children = list(getter() or ())
            except Exception:
                children = []
        except Exception:
            children = []
    for resource in children:
        try:
            path = resource.getFilePath()
        except Exception:
            continue
        key = _norm(path)
        if key and key not in found:
            found[key] = resource
    return found


def _show_scene(ui, scene):
    if scene is None:
        return
    for method_name in ("setCurrentScene", "setSceneResource"):
        method = getattr(ui, method_name, None)
        if not callable(method):
            continue
        try:
            method(scene)
            return
        except Exception:
            continue


def _link(package, factory, path, name, existing, updating):
    key = _norm(path)
    current = existing.get(key) if updating else None
    if current is not None:
        return current, False
    resource = factory.sNewFromFile(package, path, EmbedMethod.Linked)
    try:
        resource.setIdentifier(_identifier(name))
    except Exception:
        pass
    if key:
        existing[key] = resource
    return resource, True


def _import_request(payload):
    import sd
    from sd.api.sdresource import EmbedMethod
    from sd.api.sdresourcebitmap import SDResourceBitmap
    from sd.api.sdresourcescene import SDResourceScene

    app = sd.getContext().getSDApplication()
    package_mgr = app.getPackageMgr()
    ui = app.getQtForPythonUIMgr()
    updating = str(payload.get("mode") or "send") == "update"
    created = False
    package = None
    try:
        graph = ui.getCurrentGraph()
    except Exception:
        graph = None
    if graph is not None:
        try:
            package = graph.getPackage()
        except Exception:
            package = None
    if package is None:
        try:
            packages = list(package_mgr.getUserPackages() or ())
        except Exception:
            packages = []
        package = packages[0] if packages else None
    if package is None:
        if updating:
            raise RuntimeError("No Designer project is open to update")
        package = package_mgr.newUserPackage()
        created = True
        try:
            from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph

            SDSBSCompGraph.sNew(package)
        except Exception:
            traceback.print_exc()

    existing = _existing_paths(package)
    mesh = str(payload.get("mesh") or "").strip()
    map_items = []
    for item in payload.get("maps") or []:
        path = str(item.get("path") or "").strip()
        if path:
            map_items.append((path, str(item.get("name") or "Map")))
    if updating and not any(_norm(path) in existing for path in [mesh] + [path for path, _name in map_items] if path):
        raise RuntimeError("Send to Designer first")

    if mesh:
        scene, _added = _link(
            package,
            SDResourceScene,
            mesh,
            payload.get("project_name") or "Low",
            existing,
            updating,
        )
        _show_scene(ui, scene)

    imported = 0
    refreshed = 0
    for path, name in map_items:
        _bitmap, added = _link(package, SDResourceBitmap, path, name, existing, updating)
        if added:
            imported += 1
        else:
            refreshed += 1

    if updating:
        message = "Updated {0} linked map(s) and the low-poly mesh in the open Designer project".format(refreshed + imported)
    elif created:
        message = "Created a Designer project with {0} map(s) and the low-poly mesh".format(imported)
    else:
        message = "Added {0} map(s) and the low-poly mesh to the open Designer project".format(imported)
    return message


def _poll():
    global _BUSY
    if _BUSY or not REQUEST.is_file():
        return
    _BUSY = True
    try:
        payload = json.loads(REQUEST.read_text(encoding="utf-8-sig"))
        message = _import_request(payload)
    except Exception as exc:
        # Designer may still be starting. Leave the request for the next tick
        # until the sd module can see an application.
        text = str(exc)
        if "getSDApplication" in text or "getContext" in text or "NoneType" in text:
            return
        try:
            REQUEST.unlink()
        except OSError:
            pass
        _write_result(False, text or exc.__class__.__name__)
        traceback.print_exc()
        return
    else:
        try:
            REQUEST.unlink()
        except OSError:
            pass
        _write_result(True, message)
    finally:
        _BUSY = False


def initializeSDPlugin():
    global _TIMER
    try:
        QtCore = _qt()
        _TIMER = QtCore.QTimer()
        _TIMER.setInterval(500)
        _TIMER.timeout.connect(_poll)
        _TIMER.start()
        _poll()
    except Exception:
        traceback.print_exc()


def uninitializeSDPlugin():
    global _TIMER
    if _TIMER is not None:
        try:
            _TIMER.stop()
        except Exception:
            pass
        _TIMER = None
'''


def _documents_dir() -> Path:
    if sys.platform.startswith("win"):
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0 and buffer.value:
                return Path(buffer.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def coat_exchange_dir(documents: Path | None = None) -> Path:
    root = Path(documents) if documents is not None else _documents_dir()
    return root / "AppLinks" / "3D-Coat" / "Exchange"


def coat_import_lines(package: external_handoff.HandoffPackage) -> list[str]:
    """AppLink ``import.txt`` body. The mesh file must already exist before this is written."""
    mesh = Path(package.mesh_path)
    return_path = mesh.with_name(f"{mesh.stem}_3dcoat_return.obj")
    sets = {item.texture_set for item in package.maps}
    lines = [
        mesh.as_posix(),
        return_path.as_posix(),
        "[ppp]",
        "[SkipImport]",
        '[python cmd("$RoughnessMetallness")]',
    ]
    seen: set[tuple[str, str, str]] = set()
    for item in package.maps:
        command = _COAT_IMPORT_COMMANDS.get(str(item.map_type or "").strip().upper())
        if not command:
            continue
        key = (command, item.texture_set.casefold(), str(item.output_suffix or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        uv_set = item.texture_set if len(sets) > 1 else "any"
        texture = item.source_path.as_posix().replace('"', "")
        lines.append(f'[python ImportTexture("{command}","{uv_set}","{texture}")]')
    return lines


def write_coat_import(package: external_handoff.HandoffPackage, exchange_dir: Path) -> Path:
    if not Path(package.mesh_path).is_file():
        raise RuntimeError("The low-poly mesh was not exported for 3DCoat")
    folder = Path(exchange_dir)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "import.txt"
    destination.write_text("\n".join(coat_import_lines(package)) + "\n", encoding="utf-8")
    return destination


def send_package_to_3dcoat(
    executable: Path,
    package: external_handoff.HandoffPackage,
    *,
    exchange_dir: Path | None = None,
    popen_fn=None,
    running_fn=None,
) -> str:
    """Drop the low poly into 3DCoat's paint room and assign the baked maps that have slots."""
    folder = Path(exchange_dir) if exchange_dir is not None else coat_exchange_dir()
    write_coat_import(package, folder)
    running = running_fn if callable(running_fn) else external_handoff.application_is_running
    if not running(Path(executable)):
        launch = popen_fn if callable(popen_fn) else subprocess.Popen
        launch([str(Path(executable))], env=external_handoff.clean_external_environment())
    return external_handoff.TOOLBAG_HANDOFF_SENT


def _editor_label(item: external_handoff.HandoffMap, *, several_sets: bool, include_tile: bool = True) -> str:
    label = external_handoff.photoshop_layer_name(
        item.map_type,
        item.output_suffix,
        include_variant=bool(str(item.output_suffix or "").strip()),
        udim_tile=item.udim_tile if include_tile else 0,
    )
    if several_sets:
        return f"{item.texture_set} {label}"
    return label


def designer_request_dir() -> Path:
    return _documents_dir() / "FyrBaker" / "handoff"


def designer_plugin_dir() -> Path:
    return (
        _documents_dir()
        / "Adobe"
        / "Adobe Substance 3D Designer"
        / "python"
        / "sduserplugins"
        / "fyr_baker_handoff"
    )


def designer_request_payload(package: external_handoff.HandoffPackage, *, update_existing: bool = False) -> dict:
    sets = {item.texture_set for item in package.maps}
    several = len(sets) > 1
    return {
        "version": 1,
        "mode": "update" if update_existing else "send",
        "project_name": Path(package.mesh_path).stem,
        "mesh": Path(package.mesh_path).as_posix(),
        "maps": [
            {"name": _editor_label(item, several_sets=several), "path": item.source_path.as_posix()}
            for item in package.maps
        ],
    }


def install_designer_plugin(plugin_dir: Path | None = None, request_dir: Path | None = None) -> Path:
    folder = Path(plugin_dir) if plugin_dir is not None else designer_plugin_dir()
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "__init__.py"
    watched = Path(request_dir) if request_dir is not None else designer_request_dir()
    desired = (_DESIGNER_PLUGIN.strip() + "\n").replace("__FYR_REQUEST_DIR__", repr(str(watched)))
    try:
        current = script.read_text(encoding="utf-8")
    except OSError:
        current = ""
    if current != desired:
        script.write_text(desired, encoding="utf-8")
    return script


def write_designer_request(
    package: external_handoff.HandoffPackage,
    folder: Path | None = None,
    *,
    update_existing: bool = False,
) -> Path:
    if not Path(package.mesh_path).is_file():
        raise RuntimeError("The low-poly mesh was not exported for Designer")
    root = Path(folder) if folder is not None else designer_request_dir()
    root.mkdir(parents=True, exist_ok=True)
    result = root / "designer_result.json"
    if result.exists():
        result.unlink()
    request = root / "designer_request.json"
    request.write_text(json.dumps(designer_request_payload(package, update_existing=update_existing), indent=2), encoding="utf-8")
    return request


def _designer_launch_environment(plugin_dir: Path) -> dict[str, str]:
    env = external_handoff.clean_external_environment()
    root = str(Path(plugin_dir).parent)
    current = [part for part in str(env.get("SBS_DESIGNER_PYTHON_PATH", "") or "").split(os.pathsep) if part]
    if root not in current:
        current.append(root)
    env["SBS_DESIGNER_PYTHON_PATH"] = os.pathsep.join(current)
    return env


def send_package_to_designer(
    executable: Path,
    package: external_handoff.HandoffPackage,
    *,
    update_existing: bool = False,
    on_status=None,
    popen_fn=None,
    register_timer=external_handoff._UNSET,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    running_fn=None,
    request_dir: Path | None = None,
    plugin_dir: Path | None = None,
) -> str:
    """Import maps and the low poly into the open Designer package, or create one.

    Update refreshes the linked mesh and maps already in the open package. It
    needs Designer to be running, and it does not start another one.
    """
    running = running_fn if callable(running_fn) else external_handoff.application_is_running
    already_running = bool(running(Path(executable)))
    if update_existing and not already_running:
        raise RuntimeError("Designer Update requires Substance Designer to be running")
    installed = install_designer_plugin(plugin_dir, request_dir)
    request = write_designer_request(package, request_dir, update_existing=update_existing)
    result_path = request.with_name("designer_result.json")
    launch = popen_fn if callable(popen_fn) else subprocess.Popen
    process = None
    if not already_running:
        process = launch([str(Path(executable))], env=_designer_launch_environment(installed.parent))
    timeout = DESIGNER_RUNNING_TIMEOUT_SECONDS if already_running else DESIGNER_COLD_TIMEOUT_SECONDS
    deadline = now_fn() + timeout

    def _report(message: str, ok: bool) -> None:
        if callable(on_status):
            try:
                on_status(message, ok)
            except Exception:
                pass

    def _poll():
        payload = external_handoff._read_photoshop_result(result_path)
        if payload is not None:
            message = str(payload.get("message") or "").strip() or "Sent the bake to Substance Designer"
            _report(message, bool(payload.get("ok")))
            return None
        if process is not None:
            try:
                code = process.poll()
            except Exception:
                code = None
            if code is not None:
                _report("Substance Designer closed before the maps were imported", False)
                return None
        if now_fn() >= deadline:
            if already_running:
                _report(
                    "Restart Substance Designer once. The maps import when it opens",
                    False,
                )
            else:
                _report("Substance Designer did not finish importing the maps", False)
            return None
        return DESIGNER_LAUNCH_POLL_SECONDS

    if register_timer is external_handoff._UNSET:
        register = external_handoff._default_timer_register()
    elif callable(register_timer):
        register = register_timer
    else:
        register = None
    if register is None:
        while True:
            delay = _poll()
            if delay is None:
                return external_handoff.PHOTOSHOP_HANDOFF_SENT
            sleep_fn(delay)
    register(_poll, first_interval=DESIGNER_LAUNCH_POLL_SECONDS)
    return external_handoff.PHOTOSHOP_HANDOFF_LAUNCHING


_MARI_SCRIPT = '''
import json
import mari

JOB = __JOB__


def _current_project():
    current = getattr(mari.projects, "current", None)
    if not callable(current):
        return None
    try:
        return current()
    except Exception:
        return None


def _load_into_channel(channel, path, name):
    image = None
    loader = getattr(getattr(mari, "images", None), "load", None)
    if callable(loader):
        try:
            image = loader(path)
        except Exception:
            image = None
    created = None
    try:
        if image is not None:
            created = channel.createPaintableLayer(name, image)
        else:
            created = channel.createPaintableLayer(name)
    except TypeError:
        try:
            created = channel.createPaintableLayer(name)
        except Exception:
            created = None
    except Exception:
        created = None
    if created is None:
        importer = getattr(channel, "importImages", None)
        if callable(importer):
            importer(path)


def main():
    project = _current_project()
    mesh = JOB["mesh"]
    channels = JOB["channels"]
    names = [item["name"] for item in channels] or ["Color"]
    if project is None:
        mari.projects.create(JOB["project_name"], mesh, names)
    else:
        loader = getattr(getattr(mari, "geo", None), "load", None)
        if callable(loader):
            try:
                loader(mesh)
            except Exception:
                pass
    geo = mari.geo.current()
    existing = {}
    for channel in geo.channelList():
        try:
            existing[channel.name()] = channel
        except Exception:
            continue
    width = int(JOB.get("width") or 0) or 1024
    height = int(JOB.get("height") or 0) or width
    for item in channels:
        channel = existing.get(item["name"])
        if channel is None:
            channel = geo.createChannel(item["name"], width, height, int(item.get("depth") or 8))
            existing[item["name"]] = channel
        _load_into_channel(channel, item["path"], item["name"])


main()
'''


def mari_image_path(item: external_handoff.HandoffMap) -> str:
    """Mari's tile token is ``$UDIM``. Ours is ``<UDIM>``."""
    raw = item.logical_source_path or str(item.source_path)
    return str(raw).replace("\\", "/").replace("<UDIM>", "$UDIM")


def mari_channels(package: external_handoff.HandoffPackage) -> list[dict]:
    sets = {item.texture_set for item in package.maps}
    several = len(sets) > 1
    chosen: dict[tuple[str, str, str], external_handoff.HandoffMap] = {}
    order: list[tuple[str, str, str]] = []
    for item in package.maps:
        key = (item.texture_set.casefold(), item.map_type, str(item.output_suffix or "").casefold())
        current = chosen.get(key)
        if current is None:
            order.append(key)
            chosen[key] = item
        elif item.udim_tile and (not current.udim_tile or item.udim_tile < current.udim_tile):
            chosen[key] = item
    channels = []
    for key in order:
        item = chosen[key]
        channels.append(
            {
                "name": _editor_label(item, several_sets=several, include_tile=False),
                "path": mari_image_path(item),
                "depth": 8,
            }
        )
    return channels


def render_mari_script(package: external_handoff.HandoffPackage) -> str:
    width = 0
    height = 0
    for item in package.maps:
        if item.width > width:
            width = item.width
        if item.height > height:
            height = item.height
    job = {
        "project_name": Path(package.mesh_path).stem or "Bake",
        "mesh": Path(package.mesh_path).as_posix(),
        "width": width,
        "height": height or width,
        "channels": mari_channels(package),
    }
    return _MARI_SCRIPT.replace("__JOB__", repr(job), 1)


def write_mari_script(package: external_handoff.HandoffPackage) -> Path:
    if not Path(package.mesh_path).is_file():
        raise RuntimeError("The low-poly mesh was not exported for Mari")
    script = Path(package.root) / "open_in_mari.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(render_mari_script(package), encoding="utf-8")
    return script


def send_package_to_mari(
    executable: Path,
    package: external_handoff.HandoffPackage,
    *,
    popen_fn=None,
) -> str:
    """Open Mari on the low poly. An open project gains the mesh; otherwise a project is created."""
    script = write_mari_script(package)
    launch = popen_fn if callable(popen_fn) else subprocess.Popen
    launch([str(Path(executable)), str(script)], env=external_handoff.clean_external_environment())
    return external_handoff.TOOLBAG_HANDOFF_SENT
