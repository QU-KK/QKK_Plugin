# NOTE: no `from __future__ import annotations` here, deliberately.
# Blender registers operator properties by walking `cls.__annotations__` and
# checking each value for the tuple that `bpy.props.*` returns. Under PEP 563
# the annotation is never evaluated - it stays the SOURCE TEXT - so every
# property is skipped without a word of warning, and `skip_this_version` would
# silently not exist. Runtime `X | None` annotations need no future import on
# the Python that ships with the minimum supported Blender.

import json
import functools
import shutil
import sys
import tempfile
import textwrap
import threading
from pathlib import Path

import bpy

from . import device_link
from . import startup_dialogs
from . import update_policy
from . import updater_state
from .registration import safe_register_class, safe_unregister_class
from .update_archive import (
    archive_blender_version_range,
    extension_manifest_version,
    install_extension_archive,
    is_fyr_baker_archive,
    parse_version,
)

MANIFEST_URL = "https://fyrplugins.com/api/latest-version?product=baker"
MANIFEST_TIMEOUT_SECONDS = 10
DOWNLOAD_TIMEOUT_SECONDS = 120

# Where a user goes when the automatic install cannot finish. The feed may
# override it per release with a "download_page" key (an account/downloads page
# is a better landing spot than the site root), so the address can be corrected
# server-side without shipping a new build to the people who need it most.
DOWNLOAD_PAGE_URL = "https://fyrplugins.com/account"

# The mode vocabulary lives in update_policy, which every non-updater caller
# imports instead of this module: the Superhive archive ships without updater.py
# and still needs the enum to register its preference. Re-exported here so the
# updater's own code (and its tests) keep reading them off `updater`.
UPDATE_MODE_STARTUP = update_policy.UPDATE_MODE_STARTUP
UPDATE_MODE_EVERY_30_MINUTES = update_policy.UPDATE_MODE_EVERY_30_MINUTES
UPDATE_MODE_MANUAL = update_policy.UPDATE_MODE_MANUAL
UPDATE_MODE_NEVER = update_policy.UPDATE_MODE_NEVER
UPDATE_MODE_ITEMS = update_policy.UPDATE_MODE_ITEMS
UPDATE_MODE_DEFAULT = update_policy.UPDATE_MODE_DEFAULT

UPDATE_CHECK_INITIAL_DELAY_SECONDS = 3.0
# How often the timer looks in on a background manifest fetch.
UPDATE_CHECK_POLL_SECONDS = 0.25
UPDATE_CHECK_INTERVAL_SECONDS = 30.0 * 60.0
UPDATE_NOTIFY_RETRY_SECONDS = 5.0

# Width of the update popup, and how many characters of release notes fit on one
# line inside it. `WM_operator_props_dialog_popup` scales the requested width by
# both the UI scale and `widget.points / UI_DEFAULT_TEXT_POINTS`, so capacity is
# stable across UI scales - but NOT across a custom interface font, which can be
# materially wider at the same point size. The column count is therefore set
# well under the measured default-font capacity (~90 columns at width 520)
# rather than at it: a label that overflows is truncated in its middle with an
# ellipsis, silently eating words out of the middle of a sentence.
UPDATE_NOTIFICATION_DIALOG_WIDTH = 520
UPDATE_NOTES_WRAP_COLUMNS = 64

# A popup is the wrong place to read a long changelog: it has no scrollbar, and
# a tall one can run off the screen. Show the opening of the notes and send the
# rest to a text file the user's own editor can page through.
UPDATE_NOTES_MAX_LINES = 12


def wrapped_note_lines(notes: str, columns: int = UPDATE_NOTES_WRAP_COLUMNS) -> list[str]:
    """Wrap release notes so every word stays readable in the update popup.

    Blender's labels do not wrap. A line wider than the popup is truncated in
    its middle with an ellipsis, which is what turned shipped notes into
    fragments like "sit in the T...e View, Select". Wrapping here keeps the
    notes readable however they were written, so the publish side never has to
    hand-wrap them.

    Blank strings in the result mark paragraph breaks for the caller to render
    as spacing.
    """
    lines: list[str] = []
    for raw_line in str(notes or "").splitlines():
        line = raw_line.strip()
        if not line:
            # Collapse runs of blank lines into a single paragraph break, and
            # never open the block with one.
            if lines and lines[-1]:
                lines.append("")
            continue
        lines.extend(textwrap.wrap(line, width=max(1, int(columns))) or [line])
    while lines and not lines[-1]:
        lines.pop()
    return lines
def release_notes_document(result: dict | None) -> str:
    """The full release notes as a plain-text document, nothing elided.

    The popup can only ever show an excerpt. This is the copy the user's own
    text editor opens, so it carries the version header and the notes verbatim -
    original line breaks included, since the publish side writes them as
    paragraphs.
    """
    result = result or {}
    remote = str(result.get("remote_version") or "?")
    current = str(result.get("current_version") or "?")
    released_at = str(result.get("released_at") or "")

    lines = ["Fyr Baker v{:s} - release notes".format(remote), ""]
    lines.append("Installed version: v{:s}".format(current))
    if released_at:
        lines.append("Released: {:s}".format(released_at))
    lines.append("")
    lines.append("-" * 60)
    lines.append("")
    notes = str(result.get("notes") or "").strip()
    lines.append(notes if notes else "No release notes were published for this version.")
    lines.append("")
    return "\n".join(lines)


def write_release_notes_file(result: dict | None, directory: Path | None = None) -> Path | None:
    """Write the notes next to the downloaded archive; return the path or None."""
    if directory is None:
        directory = Path(tempfile.gettempdir()) / "fyr_baker_update"
    version = str((result or {}).get("remote_version") or "latest")
    safe_version = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in version)
    path = Path(directory) / "Fyr Baker v{:s} release notes.txt".format(safe_version)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(release_notes_document(result), encoding="utf-8")
    except Exception:
        return None
    return path


UPDATE_NOTIFICATION_OWNER = startup_dialogs.UPDATE_NOTIFICATION

_last_check_result: dict | None = None
_last_notified_version: str | None = None
_timer_scheduled = False
# The in-flight background manifest fetch and what it came back with.
_check_thread: threading.Thread | None = None
_pending_check_result: dict | None = None


def _parse_version(value: str | None) -> tuple[int, ...]:
    return parse_version(value)


def _package_name() -> str:
    return str(__package__ or "")


def is_extension_install() -> bool:
    """True when this code is running from a Blender Extensions package.

    Live repo installs load as ``FyrBaker`` (scripts/addons symlink). Published
    builds load as ``bl_ext.user_default.fyr_baker``. Auto-install must only run
    for the latter — installing into Extensions from the live symlink adds a
    second copy instead of replacing the repo checkout.
    """
    return _package_name().startswith("bl_ext.")


def is_live_repo_install() -> bool:
    """True only when this non-extension module is inside a Git checkout.

    Legacy add-on installs also have a plain package name, so the package name
    alone cannot identify a developer checkout. Resolving __file__ handles the
    add-on symlink used by the repository; a .git file also covers Git
    worktrees.
    """
    if is_extension_install():
        return False
    try:
        source = Path(__file__).resolve()
        return any(
            (parent / ".git").exists()
            and (parent / "addon" / "updater.py").resolve() == source
            for parent in source.parents
        )
    except (OSError, RuntimeError):
        return False


def package_repo_module(package_name: str | None = None) -> str:
    """The extension repository the running package lives in.

    Published builds load as ``bl_ext.<repo_module>.<pkg_id>``, so the repository
    is already encoded in the module path. Installing into a hard-coded
    ``user_default`` when the package actually sits in another user repository
    puts a second copy on disk while Blender keeps loading the original - which
    presents to the user as an update that "succeeds" and then changes nothing.
    """
    parts = str(package_name if package_name is not None else _package_name()).split(".")
    if len(parts) >= 3 and parts[0] == "bl_ext" and parts[1]:
        return parts[1]
    return "user_default"


def package_id(package_name: str | None = None) -> str:
    """The extension package id (its directory name inside the repository)."""
    parts = str(package_name if package_name is not None else _package_name()).split(".")
    if len(parts) >= 3 and parts[0] == "bl_ext" and parts[2]:
        return parts[2]
    return "fyr_baker"


def repo_directory(repo_module: str | None = None) -> str:
    """On-disk directory of the extension repository, or "" when unavailable."""
    module = repo_module or package_repo_module()
    try:
        repos = bpy.context.preferences.extensions.repos
    except Exception:
        return ""
    for repo in repos:
        try:
            if repo.module == module:
                return str(repo.directory or "")
        except Exception:
            continue
    return ""


def installed_package_directory() -> str:
    """Where the installed package's files live, or "" when it cannot be found."""
    directory = repo_directory()
    if not directory:
        return ""
    return str(Path(directory) / package_id())


def installed_extension_version(package_directory: str | None = None) -> tuple[int, ...]:
    """Version recorded in the INSTALLED package's manifest, read fresh from disk.

    This is the only trustworthy answer to "did the install actually land?".
    Blender's installer reports success on paths that installed nothing, so the
    updater confirms against the file the next Blender launch will read.
    """
    directory = package_directory if package_directory is not None else installed_package_directory()
    if not directory:
        return ()
    return extension_manifest_version(Path(directory))


def download_page_url(result: dict | None = None) -> str:
    if isinstance(result, dict):
        url = result.get("download_page")
        if isinstance(url, str) and url.strip().startswith(("http://", "https://")):
            return url.strip()
    return DOWNLOAD_PAGE_URL


def _get_bl_info_version() -> tuple[int, ...]:
    manifest_version = extension_manifest_version(Path(__file__).resolve().parent)
    if manifest_version:
        return manifest_version

    try:
        import importlib

        mod = sys.modules.get(__package__) or importlib.import_module(__package__)
        bl_info = getattr(mod, "bl_info", None)
        if bl_info and isinstance(bl_info.get("version"), (tuple, list)):
            return tuple(bl_info["version"])
    except Exception:
        pass

    return (0, 0, 0)


def _get_blender_version() -> tuple[int, ...]:
    return tuple(bpy.app.version)


def version_label(version: tuple[int, ...] | None) -> str:
    return ".".join(str(part) for part in (version or ()))


def blender_compatibility(
    blender_min: tuple[int, ...],
    blender_max: tuple[int, ...],
    blender_current: tuple[int, ...] | None = None,
) -> tuple[bool, str]:
    """Can THIS Blender run a build that declares ``[blender_min, blender_max)``?

    Returns ``(compatible, reason)``. ``reason`` is written for the user and is
    empty when compatible. ``blender_max`` is exclusive, matching the meaning of
    ``blender_version_max`` in Blender's own extension manifest, so a feed can
    state "released for 5.1 and 5.2" as ``blender_max_version = "5.3.0"``.

    An unknown bound never blocks: a feed row without a floor, or a Blender that
    does not report a version, compares as compatible. The install path has its
    own guard against the archive's manifest, and Blender's installer is the
    final word.
    """
    current = tuple(blender_current if blender_current is not None else _get_blender_version())
    if not current:
        return True, ""
    current_label = version_label(current)
    if blender_min and current < tuple(blender_min):
        return False, (
            "This version of Fyr Baker needs Blender {:s} or newer. "
            "You are running Blender {:s}.".format(version_label(blender_min), current_label)
        )
    if blender_max and current >= tuple(blender_max):
        return False, (
            "This version of Fyr Baker has not been released for Blender {:s}. "
            "It supports Blender versions below {:s}.".format(current_label, version_label(blender_max))
        )
    return True, ""


def current_platform_tag() -> str:
    """This machine's Blender extension platform tag, e.g. ``macos-arm64``.

    ``runtime.backend_platform_tag()`` already produces exactly Blender's tag
    vocabulary (os-arch), so the update feed and the extension manifest agree on
    one spelling instead of two.
    """
    try:
        from . import runtime

        return str(runtime.backend_platform_tag() or "").strip().lower()
    except Exception:
        return ""


#: Hosts an update archive may be downloaded and INSTALLED from without asking. The
#: installed archive is executed as addon code, so the feed naming its own download
#: location is a code-execution channel: anything that can answer for the feed (a
#: hijacked DNS entry, a proxy, a stale CDN record) could otherwise hand the installer
#: an arbitrary URL. A release served from anywhere else still reaches the artist -
#: the check below drops the automatic install back to the download page.
TRUSTED_DOWNLOAD_HOSTS = ("fyrplugins.com",)


def is_trusted_download_url(url: str | None) -> bool:
    """Whether ``url`` may be downloaded and installed without the artist's hands on it."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(str(url or "").strip())
    except Exception:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False
    return any(host == trusted or host.endswith(f".{trusted}") for trusted in TRUSTED_DOWNLOAD_HOSTS)


def select_download_url(manifest: dict, platform_tag: str | None = None) -> str | None:
    """Pick the archive this platform can actually install.

    v1 publishes two archives: the Windows build carries the native backend, and
    the macOS/Linux build carries none because those platforms bake through
    Cycles. Blender refuses to install an archive whose manifest does not list the
    running platform, so serving the wrong one is a hard install failure, not a
    degraded experience.

    A feed that only offers a flat ``download_url`` keeps working unchanged.
    """
    tag = (platform_tag or current_platform_tag()).strip().lower()

    def _trusted(url) -> str | None:
        if not isinstance(url, str) or not url.strip():
            return None
        candidate = url.strip()
        if is_trusted_download_url(candidate):
            return candidate
        # Not an error the artist can act on beyond using the download page, which is
        # exactly where a missing URL already sends them.
        print(f"[Fyr Baker] Ignoring an update download URL outside {TRUSTED_DOWNLOAD_HOSTS}: {candidate}")
        return None

    downloads = manifest.get("downloads")
    if isinstance(downloads, dict) and tag:
        url = _trusted(downloads.get(tag))
        if url:
            return url
    return _trusted(manifest.get("download_url"))


def _fetch_manifest(url: str) -> dict | None:
    import urllib.request
    import urllib.error

    # A connected install identifies itself; the manifest then carries the
    # download URL. Disconnected installs get the public metadata only.
    headers = {"User-Agent": "FyrBaker-UpdateCheck"}
    headers.update(device_link.auth_headers())
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=MANIFEST_TIMEOUT_SECONDS) as resp:
            if resp.status != 200:
                return None
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception:
        return None


def check_for_updates() -> dict:
    global _last_check_result

    manifest = _fetch_manifest(MANIFEST_URL)
    if manifest is None:
        result = {"error": True, "checked_at": _now_iso()}
        _last_check_result = result
        return result

    device_code = device_link.note_manifest_device_status(manifest)

    remote_version = _parse_version(manifest.get("version"))
    local_version = _get_bl_info_version()
    blender_min = _parse_version(manifest.get("blender_min_version"))
    blender_max = _parse_version(manifest.get("blender_max_version"))
    blender_current = _get_blender_version()

    update_available = remote_version > local_version if remote_version and local_version else False
    blender_compatible, blender_reason = blender_compatibility(blender_min, blender_max, blender_current)

    result = {
        "error": False,
        "update_available": update_available,
        "current_version": version_label(local_version),
        "remote_version": version_label(remote_version) if remote_version else manifest.get("version", ""),
        "download_url": select_download_url(manifest),
        "platform_tag": current_platform_tag(),
        "blender_version": version_label(blender_current),
        "blender_min_version": manifest.get("blender_min_version"),
        "blender_max_version": manifest.get("blender_max_version"),
        "blender_compatible": blender_compatible,
        "blender_incompatibility": blender_reason,
        "notes": manifest.get("notes"),
        "download_page": manifest.get("download_page"),
        "released_at": manifest.get("released_at"),
        "device_connected": device_link.is_connected(),
        "device_code": device_code,
        "checked_at": _now_iso(),
    }
    _last_check_result = result
    return result


def get_last_check_result() -> dict | None:
    return _last_check_result


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _download_zip(url: str, dest_path: Path) -> bool:
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FyrBaker-UpdateCheck"})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as resp:
            if resp.status != 200:
                return False
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception:
        return False


def _validate_zip(zip_path: Path) -> bool:
    return is_fyr_baker_archive(zip_path)


def _install_zip(zip_path: Path) -> bool:
    if not is_extension_install():
        return False
    return install_extension_archive(
        zip_path,
        bpy.ops.extensions.package_install_files,
        repo_module=package_repo_module(),
    )


def download_update_archive(url: str) -> dict:
    if not url:
        return {"success": False, "error": "No download URL available."}

    tmp_dir = Path(tempfile.gettempdir()) / "fyr_baker_update"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    zip_path = tmp_dir / "fyr_baker_update.zip"

    if not _download_zip(url, zip_path):
        return {"success": False, "error": "Could not download the update archive."}

    if not _validate_zip(zip_path):
        return {"success": False, "error": "The downloaded archive does not look like a valid Fyr Baker addon."}

    # The archive's own manifest is what Blender's installer enforces, and it
    # enforces it silently: an out-of-range archive "installs" with FINISHED
    # and changes nothing. Refuse here, with words, instead of there, without.
    archive_min, archive_max = archive_blender_version_range(zip_path)
    compatible, reason = blender_compatibility(archive_min, archive_max)
    if not compatible:
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
        return {"success": False, "error": reason, "blender_incompatible": True}

    return {"success": True, "zip_path": str(zip_path)}


def verify_installed_version(
    expected_version: str,
    package_directory: str,
) -> tuple[bool, str]:
    """Confirm the package on disk is now at least ``expected_version``.

    Returns ``(installed_ok, reason)``. ``reason`` is written for the user, not
    the log: it is what the recovery dialog shows when the automatic install did
    not take.
    """
    expected = parse_version(expected_version)
    if not expected:
        # Nothing to compare against; treat the operator's word as good enough
        # rather than inventing a failure.
        return True, ""

    if not package_directory:
        return False, "Blender did not report where Fyr Baker is installed."

    found = installed_extension_version(package_directory)
    if not found:
        return False, "The installed add-on folder no longer has a readable manifest."
    if found >= expected:
        return True, ""
    return False, (
        "Blender still has v{:s} installed after the update ran.".format(
            ".".join(str(part) for part in found)
        )
    )


def _install_downloaded_update(zip_path_value: str, expected_version: str = ""):
    zip_path = Path(zip_path_value)

    # Resolve the install location BEFORE the operator runs. Once Blender has
    # replaced the package, touching preference RNA from this callback is the
    # crash the comment at the bottom of this function warns about; a plain
    # string captured up front is safe to use afterwards.
    package_directory = installed_package_directory()

    ran = _install_zip(zip_path)
    if ran:
        installed, reason = verify_installed_version(expected_version, package_directory)
    else:
        installed = False
        reason = "Blender's extension installer refused to run."

    if installed:
        updater_state.clear_install_failure()
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            staging = zip_path.parent
            if staging.name.lower() == "fyr_baker_update":
                shutil.rmtree(staging, ignore_errors=True)
        except Exception:
            pass
        print("[Fyr Baker] Update installed. Restart Blender to load the new version.")
    else:
        # Keep the downloaded archive. It is the shortest path to a manual
        # install, and the recovery dialog hands the user its folder.
        updater_state.record_install_failure(
            expected_version,
            reason,
            str(zip_path),
        )
        print(
            "[Fyr Baker] Update installation failed: {:s} "
            "Use Edit > Preferences > Get Extensions > Install from Disk, "
            "and pick {:s}".format(reason or "reason unknown.", str(zip_path))
        )

    _schedule_install_outcome_report(installed)

    # Do not access bpy, registered classes, or RNA after package installation.
    # Blender may have unloaded and replaced this extension while this callback
    # was running.
    return None


def _report_install_outcome(installed: bool):
    """Show the install result once the package churn has settled.

    Reports issued from the install callback itself go to the console, never to
    the user: `bpy.ops` invoked from a timer has no window to draw a status
    message in. Both operators are resolved by ID, so this works whether the
    old build or the freshly installed one is the registered owner.
    """
    idname = "update_installed" if installed else "update_install_failed"
    try:
        getattr(bpy.ops.fyr_baker, idname)("INVOKE_DEFAULT")
    except Exception:
        pass
    return None


def _schedule_install_outcome_report(installed: bool) -> bool:
    try:
        callback = functools.partial(_report_install_outcome, bool(installed))
        bpy.app.timers.register(callback, first_interval=1.0)
        return True
    except Exception:
        return False


def schedule_downloaded_update_install(zip_path_value: str, expected_version: str = "") -> bool:
    try:
        callback = functools.partial(_install_downloaded_update, zip_path_value, expected_version)
        bpy.app.timers.register(callback, first_interval=0.5)
        return True
    except Exception:
        return False


_download_state: dict = {"thread": None, "result": None, "version": "", "url": ""}
DOWNLOAD_POLL_SECONDS = 0.25


def _run_download_in_background() -> None:
    try:
        _download_state["result"] = download_update_archive(str(_download_state.get("url") or ""))
    except Exception as exc:
        _download_state["result"] = {"success": False, "error": str(exc) or "Update download failed."}


def _download_finish_timer():
    """Main-thread tail of a background download: schedule the install, or surface the failure."""
    thread = _download_state.get("thread")
    if thread is not None and thread.is_alive():
        return DOWNLOAD_POLL_SECONDS
    _download_state["thread"] = None
    result = _download_state.get("result") or {"success": False, "error": "Update download failed."}
    _download_state["result"] = None
    version = str(_download_state.get("version") or "")
    if not result.get("success"):
        # A failed transfer is not an install failure: recording it as one would
        # route the next startup notification to the install-failed dialog for a
        # release that was never installed. Say so once, then leave the next
        # check free to offer the update again.
        _show_update_message(
            "Fyr Baker Update Download Failed",
            [str(result.get("error") or "Update download failed."), "Check your connection and try again from Preferences."],
        )
        return None
    if not schedule_downloaded_update_install(result["zip_path"], version):
        reason = "Could not schedule the update installation. Install the downloaded extension manually."
        print(f"[Fyr Baker] {reason}")
        try:
            updater_state.record_install_failure(version, reason, str(result.get("zip_path") or ""))
            bpy.ops.fyr_baker.update_install_failed("INVOKE_DEFAULT")
        except Exception:
            pass
    return None


def _show_update_message(title: str, lines: list[str]) -> None:
    """Console line plus a dismissable popup; runs from a timer, so find a window itself."""
    print(f"[Fyr Baker] {title}: {' '.join(lines)}")
    try:
        wm = bpy.context.window_manager
        windows = list(getattr(wm, "windows", None) or [])
        if not windows:
            return

        def _draw(menu, _context):
            for line in lines:
                menu.layout.label(text=line)

        with bpy.context.temp_override(window=windows[0]):
            wm.popup_menu(_draw, title=title, icon="ERROR")
    except Exception:
        pass


def start_background_update_download(url: str, version: str) -> bool:
    """Download ``url`` off the main thread; the finish timer installs it.

    The zip download waits up to DOWNLOAD_TIMEOUT_SECONDS; run inline from the
    dialog's OK it froze Blender for the whole transfer with no feedback. Returns
    False when a download is already running.
    """
    thread = _download_state.get("thread")
    if thread is not None and thread.is_alive():
        return False
    _download_state.update({"result": None, "version": str(version or ""), "url": str(url or "")})
    thread = threading.Thread(target=_run_download_in_background, name="fyr-baker-update-download", daemon=True)
    _download_state["thread"] = thread
    try:
        thread.start()
    except Exception:
        _download_state["thread"] = None
        return False
    try:
        bpy.app.timers.register(_download_finish_timer, first_interval=DOWNLOAD_POLL_SECONDS)
    except Exception:
        # No timer host (scripts, tests): finish synchronously.
        thread.join()
        _download_finish_timer()
    return True


def _run_check_in_background() -> None:
    global _pending_check_result
    try:
        _pending_check_result = check_for_updates()
    except Exception:
        _pending_check_result = {"error": True, "checked_at": _now_iso()}


def _startup_check_timer():
    global _last_notified_version, _timer_scheduled, _check_thread, _pending_check_result

    prefs = _get_prefs()
    if prefs is None:
        _timer_scheduled = False
        return None

    mode = _get_update_mode(prefs)
    if not _is_automatic_update_mode(mode):
        _timer_scheduled = False
        return None

    # The first-run settings dialog opens 1.5s after load and this timer fires at
    # 3.0s. Opening the notification over that dialog frees its block while a
    # redraw is still queued for it, which crashes Blender. Come back later —
    # before the network fetch, so waiting costs nothing.
    if startup_dialogs.is_busy(UPDATE_NOTIFICATION_OWNER):
        return UPDATE_NOTIFY_RETRY_SECONDS

    # The manifest fetch waits up to MANIFEST_TIMEOUT_SECONDS on the network. Run
    # it off the main thread: done inline from this timer it froze Blender for
    # the whole timeout on a slow or blocked connection, 3 s after every load.
    # Only the popup below has to run on the main thread.
    thread = _check_thread
    if thread is None:
        _pending_check_result = None
        thread = threading.Thread(
            target=_run_check_in_background, name="fyr-baker-update-check", daemon=True
        )
        _check_thread = thread
        try:
            thread.start()
        except Exception:
            _check_thread = None
            _timer_scheduled = False
            return None
        return UPDATE_CHECK_POLL_SECONDS
    if thread.is_alive():
        return UPDATE_CHECK_POLL_SECONDS
    _check_thread = None
    result = _pending_check_result if _pending_check_result is not None else get_last_check_result()
    _pending_check_result = None

    if result and result.get("update_available"):
        remote_version = str(result.get("remote_version") or "")
        if remote_version != _last_notified_version and not updater_state.is_version_skipped(remote_version):
            if not result.get("blender_compatible"):
                # The release exists but this Blender cannot run it. Saying so
                # is the point: staying silent leaves the user on an old build
                # with no idea that updating Blender is what unlocks the new one.
                idname = "update_blender_unsupported"
            elif updater_state.install_failed_for(remote_version):
                # An automatic install of this exact version already failed
                # once. Re-running it would fail the same way; send the user
                # straight to the manual route instead.
                idname = "update_install_failed"
            else:
                idname = "update_notify"
            try:
                getattr(bpy.ops.fyr_baker, idname)("INVOKE_DEFAULT")
                _last_notified_version = remote_version
            except Exception:
                pass

    if mode == UPDATE_MODE_EVERY_30_MINUTES:
        return UPDATE_CHECK_INTERVAL_SECONDS

    _timer_scheduled = False
    return None


def _get_prefs():
    from . import preferences
    return preferences.get_preferences()


def _get_update_mode(prefs) -> str:
    return update_policy.get_update_mode(prefs)


def _is_automatic_update_mode(mode: str) -> bool:
    return mode in update_policy.AUTOMATIC_UPDATE_MODES


def schedule_startup_check():
    global _timer_scheduled
    if _timer_scheduled:
        return
    _timer_scheduled = True
    try:
        bpy.app.timers.register(
            _startup_check_timer,
            first_interval=UPDATE_CHECK_INITIAL_DELAY_SECONDS,
        )
    except Exception:
        _timer_scheduled = False


def cancel_scheduled_check():
    global _timer_scheduled

    if not _timer_scheduled:
        return
    try:
        bpy.app.timers.unregister(_startup_check_timer)
    except Exception:
        pass
    _timer_scheduled = False


def reschedule_update_check():
    cancel_scheduled_check()

    prefs = _get_prefs()
    if prefs is not None and _is_automatic_update_mode(_get_update_mode(prefs)):
        schedule_startup_check()


class FYR_BAKER_OT_check_updates(bpy.types.Operator):
    bl_idname = "fyr_baker.check_updates"
    bl_label = "Check for Updates"
    bl_description = "Check the Fyr Plugins website for a newer version of Fyr Baker"
    bl_options = {"REGISTER"}

    _timer = None
    _thread = None
    _result: dict | None = None

    def _run_check(self):
        try:
            self._result = check_for_updates()
        except Exception:
            self._result = {"error": True, "checked_at": _now_iso()}

    def invoke(self, context, _event):
        # The manifest fetch waits up to MANIFEST_TIMEOUT_SECONDS on the network;
        # inline it froze Blender for the whole timeout on a blocked connection.
        wm = context.window_manager
        window = getattr(context, "window", None)
        if window is None or not hasattr(wm, "event_timer_add"):
            return self.execute(context)
        self._result = None
        self._thread = threading.Thread(target=self._run_check, name="fyr-baker-update-check-now", daemon=True)
        try:
            self._thread.start()
        except Exception:
            self._thread = None
            return self.execute(context)
        self._timer = wm.event_timer_add(0.2, window=window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        thread = self._thread
        if thread is not None and thread.is_alive():
            return {"RUNNING_MODAL"}
        self._release_timer(context)
        result = self._result if self._result is not None else {"error": True, "checked_at": _now_iso()}
        self._result = None
        self._thread = None
        return self._finish(result)

    def cancel(self, context):
        self._release_timer(context)
        self._thread = None

    def _release_timer(self, context):
        wm = getattr(context, "window_manager", None)
        if wm is not None and self._timer is not None:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
        self._timer = None

    def execute(self, context):
        del context
        # Direct execute (no window, scripts): the synchronous path.
        return self._finish(check_for_updates())

    def _finish(self, result):
        if result.get("error"):
            self.report({"ERROR"}, "Could not check for updates. Check your internet connection.")
            return {"CANCELLED"}

        if not result.get("update_available"):
            self.report({"INFO"}, f"Fyr Baker is up to date (v{result.get('current_version', '?')}).")
            return {"FINISHED"}

        # Asking explicitly overrides an earlier "skip this version".
        remote_version = str(result.get("remote_version") or "")
        if updater_state.is_version_skipped(remote_version):
            updater_state.clear_skipped_version()

        if not result.get("blender_compatible"):
            idname = "update_blender_unsupported"
        elif updater_state.install_failed_for(remote_version):
            idname = "update_install_failed"
        else:
            idname = "update_notify"
        try:
            getattr(bpy.ops.fyr_baker, idname)("INVOKE_DEFAULT")
        except Exception:
            if not result.get("blender_compatible"):
                self.report(
                    {"WARNING"},
                    "Fyr Baker v{:s} is available but cannot run on this Blender. {:s}".format(
                        remote_version or "?", str(result.get("blender_incompatibility") or "")
                    ).strip(),
                )
            else:
                self.report({"INFO"}, f"Update available: v{remote_version}.")

        return {"FINISHED"}


def download_availability_lines(result: dict | None) -> list[str]:
    """Why one-click install is unavailable, as short UI lines; empty when it is available."""
    result = result or {}
    if result.get("download_url"):
        return []
    if result.get("device_code") == device_link.CODE_NO_LICENSE:
        return ["Your Fyr account has no active Fyr Baker license, so the update cannot be downloaded here."]
    if result.get("device_connected"):
        return ["The download is not available for this connection right now. Use the website instead."]
    return ["Connect your Fyr account in the add-on preferences to install updates with one click."]


def draw_account_section(layout) -> None:
    """Seam for update_policy: the Fyr account block in the preferences."""
    device_link.draw_account_section(layout)


def draw_release_notes(layout, result: dict, max_lines: int = UPDATE_NOTES_MAX_LINES) -> None:
    """Draw an excerpt of the notes plus the button that opens all of them."""
    notes = result.get("notes")
    box = layout.box()
    header = box.row(align=True)
    header.label(text="Release Notes:")
    open_notes = header.row(align=True)
    open_notes.alignment = "RIGHT"
    open_notes.operator("fyr_baker.update_open_notes", text="Open Patch Notes", icon="TEXT")

    if not notes:
        box.label(text="No release notes were published for this version.")
        return

    lines = wrapped_note_lines(notes)
    shown = lines[:max_lines]
    # Never end the excerpt on a paragraph break; it reads as a rendering bug.
    while shown and not shown[-1]:
        shown.pop()

    note_col = box.column(align=True)
    note_col.scale_y = 0.9
    for line in shown:
        if line:
            note_col.label(text=line)
        else:
            note_col.separator()

    if len(lines) > len(shown):
        note_col.label(text="... Open Patch Notes to read the rest.")


class FYR_BAKER_OT_update_open_notes(bpy.types.Operator):
    bl_idname = "fyr_baker.update_open_notes"
    bl_label = "Open Patch Notes"
    bl_description = "Write the full release notes to a text file and open it in your default text editor"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        del context
        path = write_release_notes_file(get_last_check_result())
        if path is None:
            self.report({"ERROR"}, "Could not write the release notes file.")
            return {"CANCELLED"}
        try:
            bpy.ops.wm.path_open(filepath=str(path))
        except Exception:
            self.report({"WARNING"}, f"Release notes saved to {path}")
            return {"FINISHED"}
        return {"FINISHED"}


class FYR_BAKER_OT_update_open_download_page(bpy.types.Operator):
    bl_idname = "fyr_baker.update_open_download_page"
    bl_label = "Get It From The Website"
    bl_description = "Open the Fyr Plugins website, where you can sign in and download the update by hand"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        del context
        url = download_page_url(get_last_check_result())
        try:
            bpy.ops.wm.url_open(url=url)
        except Exception:
            self.report({"WARNING"}, f"Open {url} in your browser to download the update.")
            return {"FINISHED"}
        return {"FINISHED"}


class FYR_BAKER_OT_update_notify(bpy.types.Operator):
    bl_idname = "fyr_baker.update_notify"
    bl_label = "Fyr Baker Update Available"
    bl_options = {"REGISTER", "INTERNAL"}

    skip_this_version: bpy.props.BoolProperty(
        name="Skip This Version",
        description=(
            "Stop reminding me about this version. "
            "Later versions will still be offered, and Check Now in the add-on "
            "preferences always offers the newest release"
        ),
        default=False,
        options={"SKIP_SAVE"},
    )

    def invoke(self, context, event):
        del event
        registered = getattr(bpy.types, type(self).__name__, None)
        if registered is not None and registered is not type(self):
            return {"CANCELLED"}
        result = get_last_check_result()
        if result is None or not result.get("update_available"):
            return {"CANCELLED"}
        if not startup_dialogs.acquire(UPDATE_NOTIFICATION_OWNER):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(
            self,
            width=UPDATE_NOTIFICATION_DIALOG_WIDTH,
            confirm_text="Install Now",
        )

    def cancel(self, context):
        del context
        # "Later" still has to honour the checkbox, otherwise ticking Skip and
        # dismissing the popup - the obvious gesture - does nothing.
        self._apply_skip()
        startup_dialogs.release(UPDATE_NOTIFICATION_OWNER)
        return None

    def _apply_skip(self) -> bool:
        if not self.skip_this_version:
            return False
        result = get_last_check_result() or {}
        remote = str(result.get("remote_version") or "")
        if not remote:
            return False
        updater_state.set_skipped_version(remote)
        return True

    def draw(self, context):
        del context
        result = get_last_check_result()
        if result is None:
            return

        layout = self.layout
        col = layout.column()
        col.scale_y = 1.1

        current = result.get("current_version", "?")
        remote = result.get("remote_version", "?")
        col.label(text=f"A new version of Fyr Baker is available.", icon="INFO")
        col.label(text=f"Current: v{current}    New: v{remote}")
        # Every release ships a new backend build, whose GPU shaders compile on its first
        # bake (runtime.SHADER_COMPILE_NOTICE says so again in the panel).
        col.label(text="The first bake after updating takes a minute or two longer while", icon="TIME")
        col.label(text="Fyr compiles its GPU shaders. Later bakes are fast.")

        col.separator()
        draw_release_notes(col, result)

        col.separator()
        actions = col.row(align=True)
        actions.operator(
            "fyr_baker.update_open_download_page",
            text="Get It From The Website",
            icon="URL",
        )
        for line in download_availability_lines(result):
            col.label(text=line, icon="INFO")
        col.prop(self, "skip_this_version")

        if not result.get("blender_compatible"):
            col.separator()
            reason_lines = wrapped_note_lines(str(result.get("blender_incompatibility") or ""))
            col.label(text=reason_lines[0] if reason_lines else "This Blender cannot run the update.", icon="ERROR")
            for line in reason_lines[1:]:
                if line:
                    col.label(text=line)

    def execute(self, context):
        del context
        startup_dialogs.release(UPDATE_NOTIFICATION_OWNER)
        result = get_last_check_result()
        if result is None or not result.get("update_available"):
            return {"CANCELLED"}

        if self._apply_skip():
            self.report(
                {"INFO"},
                "Skipped Fyr Baker v{:s}. You will be reminded at the next release.".format(
                    str(result.get("remote_version") or "?")
                ),
            )
            return {"CANCELLED"}

        if not result.get("blender_compatible"):
            self.report(
                {"WARNING"},
                str(result.get("blender_incompatibility") or "Update skipped. This Blender cannot run it."),
            )
            return {"CANCELLED"}

        if not is_extension_install():
            if is_live_repo_install():
                print(
                    "[Fyr Baker] Live repo addon detected. Skipped auto-install; "
                    "update this checkout with git."
                )
            else:
                self.report(
                    {"WARNING"},
                    "Automatic installation requires a Blender Extension install. "
                    "Use Get It From The Website to install the update manually.",
                )
            return {"CANCELLED"}

        download_url = result.get("download_url")
        if not download_url:
            lines = download_availability_lines(result)
            self.report({"WARNING"}, " ".join(lines) if lines else "No download URL is available for this update.")
            return {"CANCELLED"}

        if not start_background_update_download(download_url, str(result.get("remote_version") or "")):
            self.report({"ERROR"}, "An update download is already running.")
            return {"CANCELLED"}
        # Deliberately not "Update installed": nothing has been installed yet.
        # The download runs on a thread and the install on a timer; each reports
        # its own verified outcome, so this message must not promise one.
        self.report({"INFO"}, "Downloading update in the background...")
        return {"FINISHED"}


class FYR_BAKER_OT_update_blender_unsupported(bpy.types.Operator):
    """Shown when a newer Fyr Baker exists but this Blender cannot run it.

    Once a release raises the Blender floor (5.1 to 5.2, say), everyone still on
    the older Blender would otherwise hear nothing at all: the popup only fired
    for installable updates, and the install itself was refused. The user needs
    to be told what is happening and that the fix is on the Blender side. There
    is deliberately no "Install Now" here.
    """

    bl_idname = "fyr_baker.update_blender_unsupported"
    bl_label = "Fyr Baker Update Needs a Different Blender"
    bl_options = {"REGISTER", "INTERNAL"}

    skip_this_version: bpy.props.BoolProperty(
        name="Skip This Version",
        description=(
            "Stop reminding me about this version. "
            "Later versions will still be offered, and Check Now in the add-on "
            "preferences always offers the newest release"
        ),
        default=False,
        options={"SKIP_SAVE"},
    )

    def invoke(self, context, event):
        del event
        registered = getattr(bpy.types, type(self).__name__, None)
        if registered is not None and registered is not type(self):
            return {"CANCELLED"}
        result = get_last_check_result()
        if result is None or not result.get("update_available") or result.get("blender_compatible"):
            return {"CANCELLED"}
        if not startup_dialogs.acquire(UPDATE_NOTIFICATION_OWNER):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(
            self,
            width=UPDATE_NOTIFICATION_DIALOG_WIDTH,
            confirm_text="Close",
        )

    def cancel(self, context):
        del context
        self._apply_skip()
        startup_dialogs.release(UPDATE_NOTIFICATION_OWNER)
        return None

    def _apply_skip(self) -> bool:
        if not self.skip_this_version:
            return False
        remote = str((get_last_check_result() or {}).get("remote_version") or "")
        if not remote:
            return False
        updater_state.set_skipped_version(remote)
        return True

    def draw(self, context):
        del context
        result = get_last_check_result()
        if result is None:
            return

        layout = self.layout
        col = layout.column()
        col.scale_y = 1.1

        current = result.get("current_version", "?")
        remote = result.get("remote_version", "?")
        col.label(text=f"Fyr Baker v{remote} is available, but this Blender cannot run it.", icon="ERROR")
        for line in wrapped_note_lines(str(result.get("blender_incompatibility") or "")):
            if line:
                col.label(text=line)

        col.separator()
        blender_min = str(result.get("blender_min_version") or "")
        if blender_min and not result.get("blender_max_version"):
            col.label(text=f"Update Blender to {blender_min} or newer to receive this release.")
        col.label(text=f"Your installed Fyr Baker v{current} keeps working as it is.")

        if result.get("notes"):
            col.separator()
            draw_release_notes(col, result)

        col.separator()
        actions = col.row(align=True)
        actions.operator(
            "fyr_baker.update_open_download_page",
            text="Open The Website",
            icon="URL",
        )
        col.prop(self, "skip_this_version")

    def execute(self, context):
        del context
        self._apply_skip()
        startup_dialogs.release(UPDATE_NOTIFICATION_OWNER)
        return {"FINISHED"}


class FYR_BAKER_OT_update_installed(bpy.types.Operator):
    bl_idname = "fyr_baker.update_installed"
    bl_label = "Restart Required"
    bl_options = {"REGISTER", "INTERNAL"}

    def invoke(self, context, event):
        del event
        registered = getattr(bpy.types, type(self).__name__, None)
        if registered is not None and registered is not type(self):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        del context
        layout = self.layout
        col = layout.column()
        col.scale_y = 1.1
        col.label(text="Fyr Baker has been updated.", icon="CHECKMARK")
        col.label(text="Please restart Blender to load the new version.")

    def execute(self, context):
        del context
        return {"FINISHED"}


class FYR_BAKER_OT_update_open_archive_folder(bpy.types.Operator):
    bl_idname = "fyr_baker.update_open_archive_folder"
    bl_label = "Show Downloaded File"
    bl_description = "Open the folder holding the update you already downloaded"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        del context
        archive = updater_state.install_failure().get("archive") or ""
        folder = str(Path(archive).parent) if archive else ""
        if not folder or not Path(folder).is_dir():
            self.report({"ERROR"}, "The downloaded update is no longer on disk.")
            return {"CANCELLED"}
        try:
            bpy.ops.wm.path_open(filepath=folder)
        except Exception:
            self.report({"WARNING"}, f"The update is in {folder}")
        return {"FINISHED"}


class FYR_BAKER_OT_update_install_failed(bpy.types.Operator):
    """Shown when the automatic install did not take.

    Without this the failure is invisible: Blender's installer reports success
    on paths that install nothing, and everything else the updater knew went to
    a console the user never opens. The result was an update popup that
    reappeared on every launch with no way to act on it and no way to stop it.
    """

    bl_idname = "fyr_baker.update_install_failed"
    bl_label = "Fyr Baker Could Not Update Itself"
    bl_options = {"REGISTER", "INTERNAL"}

    skip_this_version: bpy.props.BoolProperty(
        name="Skip This Version",
        description="Stop reminding me about this version",
        default=False,
        options={"SKIP_SAVE"},
    )

    def invoke(self, context, event):
        del event
        registered = getattr(bpy.types, type(self).__name__, None)
        if registered is not None and registered is not type(self):
            return {"CANCELLED"}
        # Opening over another startup popup frees its block while a redraw is
        # still queued for it, which crashes Blender. The failure is on disk, so
        # losing this one showing costs nothing: the next update check reopens it.
        if not startup_dialogs.acquire(UPDATE_NOTIFICATION_OWNER):
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(
            self,
            width=UPDATE_NOTIFICATION_DIALOG_WIDTH,
            confirm_text="Close",
        )

    def cancel(self, context):
        del context
        self._apply_skip()
        startup_dialogs.release(UPDATE_NOTIFICATION_OWNER)
        return None

    def _apply_skip(self) -> bool:
        if not self.skip_this_version:
            return False
        version = updater_state.install_failure().get("version") or str(
            (get_last_check_result() or {}).get("remote_version") or ""
        )
        if not version:
            return False
        updater_state.set_skipped_version(version)
        return True

    def draw(self, context):
        del context
        failure = updater_state.install_failure()
        result = get_last_check_result() or {}
        version = failure.get("version") or str(result.get("remote_version") or "?")

        layout = self.layout
        col = layout.column()
        col.scale_y = 1.1
        col.label(text=f"Fyr Baker v{version} downloaded, but Blender did not install it.", icon="ERROR")

        reason = failure.get("reason")
        if reason:
            for line in wrapped_note_lines(reason):
                if line:
                    col.label(text=line)

        col.separator()
        col.label(text="You can finish the update by hand:")
        steps = col.column(align=True)
        steps.scale_y = 0.9
        steps.label(text="1.  Edit > Preferences > Get Extensions")
        steps.label(text="2.  Install from Disk (the dropdown at the top right)")
        steps.label(text="3.  Pick the file below, then restart Blender")

        archive = failure.get("archive") or ""
        if archive:
            box = col.box()
            note_col = box.column(align=True)
            note_col.scale_y = 0.9
            for line in wrapped_note_lines(archive):
                note_col.label(text=line)

        col.separator()
        actions = col.row(align=True)
        if archive and Path(archive).is_file():
            actions.operator(
                "fyr_baker.update_open_archive_folder",
                text="Show Downloaded File",
                icon="FILE_FOLDER",
            )
        actions.operator(
            "fyr_baker.update_open_download_page",
            text="Get It From The Website",
            icon="URL",
        )
        if result.get("notes"):
            actions.operator("fyr_baker.update_open_notes", text="Open Patch Notes", icon="TEXT")

        col.prop(self, "skip_this_version")

    def execute(self, context):
        del context
        self._apply_skip()
        startup_dialogs.release(UPDATE_NOTIFICATION_OWNER)
        return {"FINISHED"}


CLASSES = (
    FYR_BAKER_OT_check_updates,
    FYR_BAKER_OT_update_open_notes,
    FYR_BAKER_OT_update_open_download_page,
    FYR_BAKER_OT_update_open_archive_folder,
    FYR_BAKER_OT_update_notify,
    FYR_BAKER_OT_update_blender_unsupported,
    FYR_BAKER_OT_update_installed,
    FYR_BAKER_OT_update_install_failed,
)


def register():
    for cls in CLASSES:
        safe_register_class(cls)
    device_link.register()

    prefs = _get_prefs()
    if prefs is not None:
        mode = _get_update_mode(prefs)
        if _is_automatic_update_mode(mode):
            schedule_startup_check()


def cancel_pending_download_install() -> None:
    """Stop the download tail from installing into an addon that is going away.

    _download_finish_timer schedules the install and Blender keeps timers across an
    addon disable, so disabling Fyr Baker while an update was downloading still
    installed the archive and re-enabled the extension underneath the user. The
    download thread itself is a daemon and its result is simply dropped.
    """
    try:
        bpy.app.timers.unregister(_download_finish_timer)
    except Exception:
        pass
    _download_state["thread"] = None
    _download_state["result"] = None


def unregister():
    cancel_scheduled_check()
    cancel_pending_download_install()
    startup_dialogs.release(UPDATE_NOTIFICATION_OWNER)
    device_link.unregister()

    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
