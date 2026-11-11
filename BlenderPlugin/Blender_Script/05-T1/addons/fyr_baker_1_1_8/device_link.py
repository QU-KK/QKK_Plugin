# NOTE: no `from __future__ import annotations` here, for the same reason as
# updater.py: Blender reads operator annotations at registration time.

"""Blender sign-in for the direct (fyrplugins.com) channel.

The website build of Fyr Baker can install its own updates, but the download
is only served to a buyer. Rather than making people paste a license key, the
add-on pairs itself with the buyer's Fyr account once:

1. ``Connect account`` asks ``/api/device/start`` for a short code and opens
   the browser at the verification page.
2. The buyer approves the code on the site while signed in.
3. The add-on polls ``/api/device/poll`` until it receives a device token,
   which it stores under Blender's config directory - deliberately outside the
   extension folder, so updates and reinstalls keep it.
4. Every update check sends that token; the manifest then carries the
   download URL and a ``device`` status the preferences UI reflects.

This module ships only with the updater. ``scripts/package_extension.py``
strips it from the Superhive build together with ``updater.py``; nothing
outside the updater imports it directly (``update_policy`` is the seam).

Every accessor is failure-tolerant: a missing or corrupt token file must
degrade to "not connected", never to an exception inside a timer.
"""

import json
import platform
import threading
import time

from . import thread_guard
from pathlib import Path

try:
    import bpy
except Exception:  # pragma: no cover - unit tests run without Blender
    bpy = None

SITE_URL = "https://fyrplugins.com"
DEVICE_START_URL = SITE_URL + "/api/device/start"
DEVICE_POLL_URL = SITE_URL + "/api/device/poll"
DEVICE_DISCONNECT_URL = SITE_URL + "/api/device/disconnect"
PRODUCT_SLUG = "baker"

#: Config subdirectory shared with updater_state and the export templates.
TOKEN_DIR_NAME = "fyr_baker"
TOKEN_FILENAME = "device_token.json"
KEY_TOKEN = "device_token"

USER_AGENT = "FyrBaker-DeviceLink"
REQUEST_TIMEOUT_SECONDS = 10
#: Used when the server does not say how often to poll / how long a code lives.
DEFAULT_POLL_SECONDS = 5.0
DEFAULT_PAIRING_SECONDS = 600.0
#: How often the main-thread timer looks at the worker's state.
UI_TICK_SECONDS = 0.5

#: Manifest ``device.code`` values the server can send.
CODE_DISCONNECTED = "device_disconnected"
CODE_NO_LICENSE = "no_license"
CODE_SIGN_IN_REQUIRED = "sign_in_required"

PHASE_STARTING = "starting"
PHASE_WAITING = "waiting"
PHASE_CONNECTED = "connected"
PHASE_FAILED = "failed"
PHASE_CANCELLED = "cancelled"

#: Tests point this at a temp file; production resolves through bpy.
_token_path_override = None

# -- token file -----------------------------------------------------------------


def token_path(create=False):
    """Absolute path of the token file, or None when Blender has no config dir."""
    if _token_path_override is not None:
        return Path(_token_path_override)
    if bpy is None:
        return None
    try:
        base = bpy.utils.user_resource("CONFIG", path=TOKEN_DIR_NAME, create=create)
    except Exception:
        return None
    if not base:
        return None
    return Path(base) / TOKEN_FILENAME


def read_token(path=None):
    """The stored device token, or "" when none is stored or the file is unreadable."""
    if path is None:
        path = token_path(create=False)
    if path is None:
        return ""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    token = payload.get(KEY_TOKEN)
    return token.strip() if isinstance(token, str) else ""


def write_token(token, path=None, **meta):
    if not isinstance(token, str) or not token.strip():
        return False
    if path is None:
        path = token_path(create=True)
    if path is None:
        return False
    payload = {KEY_TOKEN: token.strip(), "connected_at": _now_iso()}
    payload.update({key: value for key, value in meta.items() if value is not None})
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return True
    except Exception:
        return False


def clear_token(path=None):
    """Remove the token file. True when no token remains, including when none existed."""
    if path is None:
        path = token_path(create=False)
    if path is None:
        return True
    try:
        Path(path).unlink()
    except FileNotFoundError:
        return True
    except Exception:
        return False
    return True


def is_connected(path=None):
    return bool(read_token(path))


def auth_headers(path=None):
    """The Authorization header for update requests, or {} when not connected."""
    token = read_token(path)
    return {"Authorization": "Bearer " + token} if token else {}


# -- device label ---------------------------------------------------------------


def device_label():
    """A generic label for the account page: Blender version and OS family only.

    Deliberately no hostname, user name, or hardware id - the label exists so
    the buyer can tell two installs apart on the account page, nothing more.
    """
    system = platform.system()
    os_name = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(system, system or "Unknown OS")
    version = ""
    if bpy is not None:
        try:
            version = "{:d}.{:d}".format(*bpy.app.version[:2])
        except Exception:
            version = ""
    return ("Blender " + version + " on " + os_name).replace("  ", " ").strip()


# -- HTTP -----------------------------------------------------------------------


def _urlopen(request, timeout):
    import urllib.request

    return urllib.request.urlopen(request, timeout=timeout)


def _post_json(url, payload, headers=None, timeout=REQUEST_TIMEOUT_SECONDS):
    """POST JSON and return ``(status, body_dict)``. Network failure is ``(0, {...})``."""
    import urllib.request
    import urllib.error

    body = json.dumps(payload or {}).encode("utf-8")
    request_headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with _urlopen(request, timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw = response.read()
    except urllib.error.HTTPError as error:
        status = int(error.code)
        try:
            raw = error.read()
        except Exception:
            raw = b""
        finally:
            try:
                error.close()
            except Exception:
                pass
    except Exception as error:
        return 0, {"error": "Could not reach fyrplugins.com ({:s}).".format(type(error).__name__)}

    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        parsed = {}
    return status, parsed if isinstance(parsed, dict) else {}


def start_pairing(product=PRODUCT_SLUG):
    """Ask the site for a pairing. Returns the server payload, or ``{"error": ...}``."""
    status, body = _post_json(DEVICE_START_URL, {"product": product, "label": device_label()})
    if status == 200 and isinstance(body.get("device_code"), str) and isinstance(body.get("user_code"), str):
        return body
    return {"error": str(body.get("error") or "The website did not return a pairing code (HTTP {:d}).".format(status))}


def poll_pairing(device_code):
    """One poll. Always returns a dict with a ``status`` key."""
    status, body = _post_json(DEVICE_POLL_URL, {"device_code": device_code})
    if status == 0:
        return {"status": "network_error", "error": body.get("error", "")}
    state = body.get("status")
    if not isinstance(state, str):
        state = "error"
    body["status"] = state
    body["http_status"] = status
    return body


def disconnect_remote(token):
    """Tell the site this token is done. Best effort; the local file is cleared regardless."""
    if not token:
        return False
    status, _body = _post_json(DEVICE_DISCONNECT_URL, {}, headers={"Authorization": "Bearer " + token})
    return status == 200


# -- manifest status ------------------------------------------------------------

_last_device_code = ""


def note_manifest_device_status(manifest, path=None):
    """Record what the manifest said about our token; drop a revoked token.

    Returns the ``device.code`` string (``""`` when the manifest carried none).
    """
    global _last_device_code
    device = manifest.get("device") if isinstance(manifest, dict) else None
    code = ""
    if isinstance(device, dict):
        raw = device.get("code")
        code = raw if isinstance(raw, str) else ""
        if code == CODE_DISCONNECTED and is_connected(path):
            # The site revoked this machine (account page, refund, or the
            # token was never valid). Keeping the file would resend a dead
            # token forever and hide the "Connect account" button.
            clear_token(path)
    _last_device_code = code
    return code


def last_device_code():
    return _last_device_code


# -- pairing state machine ------------------------------------------------------

_pairing = None
_pairing_lock = threading.Lock()
#: Bumped (under the lock) when a pairing starts or is cancelled. A worker acts
#: only while the generation it started with is current: Connect -> Cancel ->
#: Connect can leave the old thread alive, and a phase check alone cannot tell
#: its cancelled pairing from the new one.
_pairing_generation = 0
_pairing_thread = None
_ui_timer_registered = False


def pairing_state():
    """A copy of the current pairing, or None when no pairing is in progress or finished."""
    with _pairing_lock:
        return dict(_pairing) if _pairing else None


def _set_pairing(generation=None, **changes):
    """Update the pairing; with ``generation``, only while that pairing is still current."""
    with _pairing_lock:
        if _pairing is None or (generation is not None and generation != _pairing_generation):
            return False
        _pairing.update(changes)
        return True


def _waiting_state(generation):
    """A copy of the pairing while it is ``generation`` and waiting for approval, else None."""
    with _pairing_lock:
        if _pairing is None or generation != _pairing_generation or _pairing.get("phase") != PHASE_WAITING:
            return None
        return dict(_pairing)


def pairing_active():
    state = pairing_state()
    return bool(state) and state.get("phase") in (PHASE_STARTING, PHASE_WAITING)


def clear_pairing():
    """Forget a finished pairing so the preferences fall back to the idle view."""
    global _pairing
    if pairing_active():
        return
    with _pairing_lock:
        _pairing = None


def _now_iso():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _run_pairing_worker(sleep=time.sleep, clock=time.monotonic, generation=None):
    """The whole pairing on a worker thread: start, then poll until terminal.

    Never touches ``bpy``; the main-thread timer reads the state and opens the
    browser. ``sleep``/``clock`` are injectable so tests run instantly.
    ``generation`` is the pairing this worker owns (default: the current one);
    every read and write below is a no-op once another pairing replaced it.
    """
    if generation is None:
        with _pairing_lock:
            generation = _pairing_generation
    started = start_pairing()
    if started.get("error"):
        _set_pairing(generation, phase=PHASE_FAILED, message=str(started["error"]))
        return

    interval = float(started.get("interval") or DEFAULT_POLL_SECONDS)
    lifetime = float(started.get("expires_in") or DEFAULT_PAIRING_SECONDS)
    deadline = clock() + lifetime
    _set_pairing(
        generation,
        phase=PHASE_WAITING,
        device_code=started["device_code"],
        user_code=started["user_code"],
        verification_url=str(started.get("verification_url") or (SITE_URL + "/account/connect?code=" + started["user_code"])),
        browser_pending=True,
        message="",
    )

    while True:
        if _waiting_state(generation) is None:
            return
        if clock() > deadline:
            _set_pairing(generation, phase=PHASE_FAILED, message="The code expired before it was approved. Try again.")
            return

        sleep(interval)

        state = _waiting_state(generation)
        if state is None:
            return

        result = poll_pairing(state["device_code"])
        status = result.get("status")
        if status == "pending" or status == "network_error":
            # A network blip should not abandon an approval that may be seconds away.
            continue
        if _waiting_state(generation) is None:
            # Cancelled or replaced during the request: the result is not ours to store.
            return
        if status == "approved":
            token = result.get("device_token")
            if isinstance(token, str) and token.strip() and write_token(token, product=result.get("product") or PRODUCT_SLUG):
                _set_pairing(generation, phase=PHASE_CONNECTED, message="Connected to your Fyr account.", device_code="")
            else:
                _set_pairing(generation, phase=PHASE_FAILED, message="Could not save the connection. Check that Blender can write to its config folder.")
            return
        if status == "expired":
            _set_pairing(generation, phase=PHASE_FAILED, message="The code expired before it was approved. Try again.")
            return
        if status == "revoked":
            _set_pairing(generation, phase=PHASE_FAILED, message="This connection was cancelled on the website. Try again.")
            return
        # claimed, unknown, error: the code cannot be used any more.
        _set_pairing(generation, phase=PHASE_FAILED, message=str(result.get("error") or "The code is no longer valid. Try again."))
        return


def begin_pairing():
    """Start a pairing; False when one is already in progress."""
    global _pairing, _pairing_generation, _pairing_thread
    if pairing_active():
        return False
    with _pairing_lock:
        _pairing_generation += 1
        generation = _pairing_generation
        _pairing = {"phase": PHASE_STARTING, "message": "", "user_code": "", "verification_url": "", "browser_pending": False}
    thread = threading.Thread(target=thread_guard.guarded(_run_pairing_worker, "device-link"), kwargs={"generation": generation}, name="fyr-baker-device-link", daemon=True)
    _pairing_thread = thread
    try:
        thread.start()
    except Exception:
        _pairing_thread = None
        _set_pairing(generation, phase=PHASE_FAILED, message="Could not start the connection.")
        return False
    _ensure_ui_timer()
    return True


def cancel_pairing():
    global _pairing_generation
    with _pairing_lock:
        if _pairing is None or _pairing.get("phase") not in (PHASE_STARTING, PHASE_WAITING):
            return False
        # Retire the worker too, so a start request still in flight cannot
        # flip the cancelled pairing back to waiting.
        _pairing_generation += 1
        _pairing.update(phase=PHASE_CANCELLED, message="", browser_pending=False)
    return True


def open_verification_page():
    """(Re)open the browser at the approval page. False when there is nothing to open."""
    state = pairing_state()
    url = (state or {}).get("verification_url")
    if not url:
        return False
    _set_pairing(browser_pending=False)
    if bpy is None:
        return False
    try:
        bpy.ops.wm.url_open(url=url)
    except Exception:
        return False
    return True


def _redraw_preferences():
    if bpy is None:
        return
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "PREFERENCES":
                    area.tag_redraw()
    except Exception:
        pass


def _ui_timer():
    """Main-thread tick: open the browser once the code exists, keep the UI fresh."""
    global _ui_timer_registered
    state = pairing_state()
    if state is None:
        _ui_timer_registered = False
        return None
    if state.get("browser_pending") and state.get("verification_url"):
        open_verification_page()
    _redraw_preferences()
    if state.get("phase") in (PHASE_STARTING, PHASE_WAITING):
        return UI_TICK_SECONDS
    _ui_timer_registered = False
    return None


def _ensure_ui_timer():
    global _ui_timer_registered
    if _ui_timer_registered or bpy is None:
        return
    try:
        bpy.app.timers.register(_ui_timer, first_interval=UI_TICK_SECONDS)
        _ui_timer_registered = True
    except Exception:
        _ui_timer_registered = False


def _cancel_ui_timer():
    global _ui_timer_registered
    if not _ui_timer_registered or bpy is None:
        return
    try:
        bpy.app.timers.unregister(_ui_timer)
    except Exception:
        pass
    _ui_timer_registered = False


def disconnect():
    """Forget the token locally and tell the site, off the main thread."""
    token = read_token()
    cleared = clear_token()
    if token:
        threading.Thread(target=thread_guard.guarded(disconnect_remote, "device-unlink"), args=(token,), name="fyr-baker-device-unlink", daemon=True).start()
    global _last_device_code
    _last_device_code = ""
    clear_pairing()
    return cleared


# -- preferences UI -------------------------------------------------------------


def draw_account_section(layout):
    """The "Fyr account" block inside the Updates section of the preferences."""
    col = layout.column()
    state = pairing_state()
    phase = (state or {}).get("phase")

    if is_connected():
        row = col.row(align=True)
        row.label(text="Connected to your Fyr account. Updates install with one click.", icon="CHECKMARK")
        if last_device_code() == CODE_NO_LICENSE:
            col.label(text="This account has no active Fyr Baker license, so updates cannot be downloaded.", icon="ERROR")
        col.operator("fyr_baker.device_disconnect", text="Disconnect", icon="UNLINKED")
        return

    if phase in (PHASE_STARTING, PHASE_WAITING):
        code = (state or {}).get("user_code") or ""
        if code:
            col.label(text="Your code: " + code, icon="LINKED")
            col.label(text="Approve it in the browser window that opened, then come back here.")
        else:
            col.label(text="Asking fyrplugins.com for a code...", icon="LINKED")
        row = col.row(align=True)
        row.operator("fyr_baker.device_open_browser", text="Open Browser Again", icon="URL")
        row.operator("fyr_baker.device_cancel_pairing", text="Cancel", icon="X")
        return

    if phase == PHASE_FAILED:
        col.label(text=(state or {}).get("message") or "The connection did not complete.", icon="ERROR")
        col.operator("fyr_baker.device_connect", text="Try Again", icon="LINKED")
        return

    if phase == PHASE_CONNECTED:
        # The token exists but is_connected() said no: the file vanished.
        col.label(text="The connection was lost. Connect again.", icon="ERROR")

    col.label(text="Connect your Fyr account to install updates with one click.", icon="INFO")
    col.operator("fyr_baker.device_connect", text="Connect Account", icon="LINKED")


# -- operators ------------------------------------------------------------------

if bpy is not None:

    class FYR_BAKER_OT_device_connect(bpy.types.Operator):
        bl_idname = "fyr_baker.device_connect"
        bl_label = "Connect Fyr Account"
        bl_description = (
            "Open fyrplugins.com to connect this Blender to your Fyr account, "
            "so Fyr Baker updates install with one click"
        )
        bl_options = {"REGISTER", "INTERNAL"}

        def execute(self, context):
            del context
            if not begin_pairing():
                self.report({"WARNING"}, "A connection is already in progress.")
                return {"CANCELLED"}
            self.report({"INFO"}, "Approve the code in your browser to finish connecting.")
            return {"FINISHED"}

    class FYR_BAKER_OT_device_open_browser(bpy.types.Operator):
        bl_idname = "fyr_baker.device_open_browser"
        bl_label = "Open Approval Page"
        bl_description = "Open the approval page in your browser again"
        bl_options = {"REGISTER", "INTERNAL"}

        def execute(self, context):
            del context
            if not open_verification_page():
                self.report({"WARNING"}, "There is no approval page to open yet.")
                return {"CANCELLED"}
            return {"FINISHED"}

    class FYR_BAKER_OT_device_cancel_pairing(bpy.types.Operator):
        bl_idname = "fyr_baker.device_cancel_pairing"
        bl_label = "Cancel Connection"
        bl_description = "Stop waiting for approval"
        bl_options = {"REGISTER", "INTERNAL"}

        def execute(self, context):
            del context
            cancel_pairing()
            clear_pairing()
            return {"FINISHED"}

    class FYR_BAKER_OT_device_disconnect(bpy.types.Operator):
        bl_idname = "fyr_baker.device_disconnect"
        bl_label = "Disconnect Fyr Account"
        bl_description = "Forget the connection on this computer and remove it from your Fyr account"
        bl_options = {"REGISTER", "INTERNAL"}

        def execute(self, context):
            del context
            if not disconnect():
                self.report({"ERROR"}, "Could not remove the stored connection. Delete it by hand from Blender's config folder.")
                return {"CANCELLED"}
            self.report({"INFO"}, "Disconnected from your Fyr account.")
            return {"FINISHED"}

    CLASSES = (
        FYR_BAKER_OT_device_connect,
        FYR_BAKER_OT_device_open_browser,
        FYR_BAKER_OT_device_cancel_pairing,
        FYR_BAKER_OT_device_disconnect,
    )
else:
    CLASSES = ()


def register():
    if bpy is None:
        return
    from .registration import safe_register_class

    for cls in CLASSES:
        safe_register_class(cls)


def unregister():
    cancel_pairing()
    _cancel_ui_timer()
    if bpy is None:
        return
    from .registration import safe_unregister_class

    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
