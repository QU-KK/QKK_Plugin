from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path


def format_backend_log(
    *,
    title: str,
    backend_path: str | Path | None,
    command: list[str],
    cwd: str | Path,
    returncode: int,
    stdout: str,
    stderr: str,
    backend_version: str = "",
    note: str = "",
    protocol_version: str,
    list2cmdline_fn,
) -> str:
    backend_path_text = str(Path(backend_path)) if backend_path is not None else "unknown"
    command_text = list2cmdline_fn([str(item) for item in command]) if command else ""
    lines = [
        f"title: {title}",
        f"timestamp_utc: {datetime.now(timezone.utc).isoformat()}",
        f"backend_path: {backend_path_text}",
        f"backend_version: {backend_version or 'unknown'}",
        f"addon_protocol: {protocol_version}",
        f"command: {command_text}",
        f"cwd: {cwd}",
        f"returncode: {returncode}",
    ]
    if note:
        lines.append(f"note: {note}")
    lines.extend(
        [
            "",
            "[stdout]",
            stdout.rstrip("\n"),
            "",
            "[stderr]",
            stderr.rstrip("\n"),
            "",
        ]
    )
    return "\n".join(lines)


def write_backend_log(
    log_path: str | Path,
    *,
    title: str,
    backend_path: str | Path | None,
    command: list[str],
    cwd: str | Path,
    returncode: int,
    stdout: str,
    stderr: str,
    backend_version: str = "",
    note: str = "",
    format_backend_log_fn,
    write_text_atomic_fn,
) -> Path:
    path = Path(log_path)
    write_text_atomic_fn(
        path,
        format_backend_log_fn(
            title=title,
            backend_path=backend_path,
            command=command,
            cwd=cwd,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            backend_version=backend_version,
            note=note,
        ),
    )
    return path


def append_live_log(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(text)


def live_log_time_text(moment: datetime | None = None) -> str:
    resolved = moment if moment is not None else datetime.now(timezone.utc).astimezone()
    return resolved.strftime("%H:%M:%S")


def short_log_path(path: str | Path | None, *, parts: int = 2) -> str:
    raw_path = str(path or "").strip()
    if not raw_path:
        return ""
    try:
        resolved = Path(raw_path)
        selected_parts = resolved.parts[-max(1, int(parts)):]
        return str(Path(*selected_parts))
    except Exception:
        return raw_path


def append_live_log_block(path: str | Path, title: str, details: list[str] | tuple[str, ...] | None = None) -> None:
    lines = [f"[{live_log_time_text()}] {title}"]
    for detail in details or ():
        detail_text = str(detail or "").strip()
        if detail_text:
            lines.append(f"  {detail_text}")
    append_live_log(path, "\n".join(lines) + "\n\n")


def copyable_log_window_enabled(*, get_preferences_fn) -> bool:
    addon_preferences = get_preferences_fn()
    return bool(getattr(addon_preferences, "open_backend_log_window", False)) if addon_preferences is not None else False


def powershell_executable(*, os_environ) -> str:
    system_root = os_environ.get("SystemRoot", r"C:\Windows")
    candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if candidate.exists():
        return str(candidate)
    return "powershell.exe"


def powershell_single_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def log_viewer_state_path(log_path: str | Path) -> Path:
    resolved_path = Path(log_path).expanduser()
    return resolved_path.with_name(f"{resolved_path.name}.viewer.json")


def process_is_alive(pid: int, *, os_name: str, os_module) -> bool:
    if int(pid) <= 0:
        return False
    if os_name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os_module.kill(int(pid), 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_log_viewer_state(log_path: str | Path, *, log_viewer_state_path_fn) -> dict[str, object]:
    state_path = log_viewer_state_path_fn(log_path)
    if not state_path.exists():
        return {}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        try:
            state_path.unlink()
        except Exception:
            pass
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def write_log_viewer_state(log_path: str | Path, *, pid: int, host_pid: int, title: str, write_text_atomic_fn, log_viewer_state_path_fn) -> None:
    write_text_atomic_fn(
        log_viewer_state_path_fn(log_path),
        json.dumps(
            {
                "pid": int(pid),
                "host_pid": int(host_pid),
                "title": str(title or ""),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ),
    )


def remove_log_viewer_state(log_path: str | Path, *, log_viewer_state_path_fn) -> None:
    state_path = log_viewer_state_path_fn(log_path)
    try:
        if state_path.exists():
            state_path.unlink()
    except Exception:
        pass


def existing_log_viewer_running(
    log_path: str | Path,
    *,
    viewers: dict[str, object],
    os_module,
    read_log_viewer_state_fn,
    process_is_alive_fn,
    remove_log_viewer_state_fn,
) -> bool:
    resolved_path = Path(log_path).expanduser()
    key = os_module.path.normcase(str(resolved_path))
    existing = viewers.get(key)
    if existing is not None:
        try:
            if existing.poll() is None:
                return True
        except Exception:
            pass
        viewers.pop(key, None)
        remove_log_viewer_state_fn(resolved_path)

    state = read_log_viewer_state_fn(resolved_path)
    viewer_pid = int(state.get("pid", 0) or 0)
    if process_is_alive_fn(viewer_pid):
        return True
    if viewer_pid:
        remove_log_viewer_state_fn(resolved_path)
    return False


def open_backend_log_window(
    log_path: str | Path,
    *,
    title: str = "Fyr Baker Backend Log",
    follow: bool = True,
    viewers: dict[str, object],
    os_module,
    subprocess_module,
    powershell_executable_fn,
    powershell_single_quote_fn,
    log_viewer_state_path_fn,
    existing_log_viewer_running_fn,
    write_log_viewer_state_fn,
) -> bool:
    if os_module.name != "nt":
        return False

    resolved_path = Path(log_path).expanduser()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.touch(exist_ok=True)
    if existing_log_viewer_running_fn(resolved_path):
        return True

    state_path = log_viewer_state_path_fn(resolved_path)
    host_pid = os_module.getpid()
    tail_command = "Get-Content -Path $path -Tail 200 -Wait" if follow else "Get-Content -Path $path -Tail 200"
    command = (
        f"$Host.UI.RawUI.WindowTitle = {powershell_single_quote_fn(title)}; "
        f"$path = {powershell_single_quote_fn(str(resolved_path))}; "
        f"$statePath = {powershell_single_quote_fn(str(state_path))}; "
        f"$hostPid = {int(host_pid)}; "
        "$watcher = Start-Job -ArgumentList $hostPid, $PID, $statePath -ScriptBlock { "
        "param($trackedHostPid, $viewerPid, $trackedStatePath) "
        "try { while (Get-Process -Id $trackedHostPid -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 500 } } "
        "finally { Remove-Item -Path $trackedStatePath -ErrorAction SilentlyContinue; Stop-Process -Id $viewerPid -Force } "
        "}; "
        "try { "
        "Write-Output ('Watching: ' + [System.IO.Path]::GetFileName($path)); "
        "Write-Output ('Path: ' + $path); "
        "Write-Output ''; "
        f"{tail_command}; "
        "} finally { "
        "Stop-Job $watcher -ErrorAction SilentlyContinue | Out-Null; "
        "Remove-Job $watcher -ErrorAction SilentlyContinue | Out-Null; "
        "Remove-Item -Path $statePath -ErrorAction SilentlyContinue; "
        "}"
    )
    creation_flags = int(getattr(subprocess_module, "CREATE_NEW_CONSOLE", 0))
    try:
        viewer = subprocess_module.Popen(
            [
                powershell_executable_fn(),
                "-NoExit",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=str(resolved_path.parent),
            creationflags=creation_flags,
        )
    except Exception:
        return False

    key = os_module.path.normcase(str(resolved_path))
    viewers[key] = viewer
    try:
        write_log_viewer_state_fn(resolved_path, pid=int(getattr(viewer, "pid", 0) or 0), host_pid=host_pid, title=title)
    except Exception:
        pass
    return True


def maybe_open_backend_log_window(
    log_path: str | Path,
    *,
    title: str,
    follow: bool = True,
    copyable_log_window_enabled_fn,
    open_backend_log_window_fn,
) -> bool:
    if not copyable_log_window_enabled_fn():
        return False
    return open_backend_log_window_fn(log_path, title=title, follow=follow)
