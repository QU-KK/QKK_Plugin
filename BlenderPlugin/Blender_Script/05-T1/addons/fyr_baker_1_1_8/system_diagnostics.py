"""Machine facts for the support bundle that the backend cannot report.

``fyr_baker_backend capabilities --json`` names the ONE adapter the backend picked.
A report like "No D3D12-capable hardware adapter until Blender restarted" or "the
backend baked on the AMD iGPU next to a 4090" needs every adapter, its driver in
the vendor's own numbering, the per-app GPU preference Windows applies to Blender
and the backend, and the recent display-driver resets (System log driver events
plus WER LiveKernelEvent reports from the Application log). This module collects those
from stock Windows tools, read-only, with every probe time-bounded and every
failure recorded as text instead of raised.

Runs on whatever thread builds the bundle (today the operator, on Blender's main
thread), so the subprocess probes run concurrently: the whole collection costs
roughly one PowerShell start (~0.5-1 s) and is capped by ``PROBE_TIMEOUT_S``.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import threading
import time

SCHEMA = "fyr_baker_system_info"
SCHEMA_VERSION = 1
ARCHIVE_PATH = "system/gpu_info.json"

PROBE_TIMEOUT_S = 10.0
TOTAL_DEADLINE_S = 20.0
EVENT_WINDOW_DAYS = 14
EVENT_MAX_ENTRIES = 50
EVENT_MESSAGE_CHARS = 300

EVENT_PROVIDERS = (
    "nvlddmkm",
    "Display",
    "amdkmdag",
    "amdwddmg",
    "Microsoft-Windows-WER-SystemErrorReporting",
)
LIVE_KERNEL_PROVIDER = "Windows Error Reporting"
LIVE_KERNEL_EVENT_ID = 1001
LIVE_KERNEL_WINDOW_DAYS = 14
LIVE_KERNEL_MAX_ENTRIES = 20
# WER 1001 rows scanned (newest first) before the LiveKernelEvent filter; keeps an
# app-crash-heavy log from making the probe unbounded.
LIVE_KERNEL_SCAN_LIMIT = 500
WER_KEY = r"SOFTWARE\Microsoft\Windows\Windows Error Reporting"
WER_POLICY_KEY = r"SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting"
GPU_PREFERENCE_EXES = ("blender.exe", "blender-launcher.exe", "fyr_baker_backend.exe")

DISPLAY_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
GPU_PREFERENCES_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
WINDOWS_CURRENT_VERSION_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"

VENDOR_NAMES = {
    "10DE": "NVIDIA",
    "1002": "AMD",
    "1022": "AMD",
    "8086": "Intel",
    "1414": "Microsoft",
    "5143": "Qualcomm",
}
EVENT_LEVEL_NAMES = {0: "LogAlways", 1: "Critical", 2: "Error", 3: "Warning", 4: "Information", 5: "Verbose"}
GPU_PREFERENCE_MEANINGS = {"0": "let Windows decide", "1": "power saving", "2": "high performance"}

# Win32_VideoController.AdapterRAM is a uint32: every card with >= 4 GiB reports
# 0xFFF00000 or thereabouts, which is why the registry's 64-bit value is read too.
_ADAPTER_RAM_CAP = 0xFFF00000

_PNP_VENDOR_RE = re.compile(r"VEN_([0-9A-Fa-f]{4})")
_DOTNET_DATE_RE = re.compile(r"/Date\((-?\d+)")
_CIM_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})\d{6}")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


# --------------------------------------------------------------------------- parsing


def nvidia_version_from_windows_driver(driver_version: str) -> str:
    """``32.0.16.1062`` -> ``610.62``: NVIDIA's number is the last five digits of
    the last two Windows components. Returns "" when the input does not fit."""
    parts = str(driver_version or "").strip().split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts[2:]):
        return ""
    digits = (parts[2] + parts[3].zfill(4))[-5:]
    if len(digits) != 5:
        return ""
    return f"{int(digits[:3])}.{digits[3:]}"


def vendor_from_pnp_id(pnp_device_id: str) -> tuple[str, str]:
    """``(vendor_id, vendor_name)`` from a PNP device id such as ``PCI\\VEN_10DE&...``."""
    text = str(pnp_device_id or "")
    match = _PNP_VENDOR_RE.search(text)
    if match:
        vendor_id = match.group(1).upper()
        return vendor_id, VENDOR_NAMES.get(vendor_id, "unknown")
    if text.upper().startswith(("ROOT\\", "SWD\\")):
        return "", "virtual"
    return "", "unknown"


def normalize_driver_date(value) -> str:
    """ISO date from the shapes Windows PowerShell 5.1 / 7 / CIM emit for DriverDate."""
    if value in (None, ""):
        return ""
    if isinstance(value, dict):  # PS 7 can serialize DateTime as {"value": ..., "DateTime": ...}
        value = value.get("value") or value.get("DateTime") or ""
    text = str(value).strip()
    match = _DOTNET_DATE_RE.search(text)
    if match:
        try:
            stamp = datetime.fromtimestamp(int(match.group(1)) / 1000.0, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return text
        return stamp.date().isoformat()
    for pattern in (_ISO_DATE_RE, _CIM_DATE_RE):
        match = pattern.match(text)
        if match:
            return "-".join(match.groups())
    return text


def _json_records(stdout: str) -> list[dict]:
    """ConvertTo-Json emits nothing for no rows, an object for one, a list for many."""
    text = (stdout or "").strip().lstrip("\ufeff")
    if not text:
        return []
    payload = json.loads(text)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_video_controllers(stdout: str) -> list[dict]:
    adapters = []
    for record in _json_records(stdout):
        pnp_id = str(record.get("PNPDeviceID") or "")
        vendor_id, vendor = vendor_from_pnp_id(pnp_id)
        driver_version = str(record.get("DriverVersion") or "")
        adapter_ram = _as_int(record.get("AdapterRAM"))
        adapter = {
            "name": str(record.get("Name") or ""),
            "vendor": vendor,
            "vendor_id": vendor_id,
            "pnp_device_id": pnp_id,
            "driver_version": driver_version,
            "driver_date": normalize_driver_date(record.get("DriverDate")),
            "adapter_ram_bytes": adapter_ram,
            "adapter_ram_capped_32bit": bool(adapter_ram is not None and adapter_ram >= _ADAPTER_RAM_CAP),
            "status": str(record.get("Status") or ""),
            "video_processor": str(record.get("VideoProcessor") or ""),
        }
        if vendor == "NVIDIA":
            adapter["nvidia_driver_version"] = nvidia_version_from_windows_driver(driver_version)
        adapters.append(adapter)
    return adapters


def parse_display_events(stdout: str) -> list[dict]:
    events = []
    for record in _json_records(stdout)[:EVENT_MAX_ENTRIES]:
        level = _as_int(record.get("Level"))
        events.append(
            {
                "time": str(record.get("TimeCreated") or ""),
                "provider": str(record.get("ProviderName") or ""),
                "event_id": _as_int(record.get("Id")),
                "level": EVENT_LEVEL_NAMES.get(level, str(record.get("LevelDisplayName") or level or "")),
                "message": " ".join(str(record.get("Message") or "").split())[:EVENT_MESSAGE_CHARS],
            }
        )
    return events


def summarize_events(events: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for event in events:
        key = f"{event.get('provider', '')}/{event.get('event_id')}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def parse_nvidia_smi(stdout: str) -> list[dict]:
    rows = []
    for line in (stdout or "").splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) < 4 or not fields[0]:
            continue
        rows.append(
            {"name": fields[0], "driver_version": fields[1], "memory_total": fields[2], "pstate": fields[3]}
        )
    return rows


def parse_gpu_preference(value: str) -> dict:
    fields = {}
    for part in str(value or "").split(";"):
        key, sep, raw = part.partition("=")
        if sep and key.strip():
            fields[key.strip()] = raw.strip()
    parsed = {"raw": str(value or ""), "fields": fields}
    preference = fields.get("GpuPreference")
    if preference is not None:
        parsed["meaning"] = GPU_PREFERENCE_MEANINGS.get(preference, "other")
    return parsed


# --------------------------------------------------------------------------- redaction


def _redaction_pairs() -> list[tuple[re.Pattern, str]]:
    pairs = []
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    if home and home not in ("~", "\\", "/"):
        for variant in {home, home.replace("\\", "/")}:
            pairs.append((re.compile(re.escape(variant), re.IGNORECASE), "%USERPROFILE%"))
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if len(user) >= 2:
        pairs.append(
            (re.compile(r"([\\/]Users[\\/])" + re.escape(user) + r"(?=[\\/]|$)", re.IGNORECASE), r"\1%USERNAME%")
        )
    return pairs


def redact(value, pairs=None):
    """Replace the user profile path / account name in every string of ``value``."""
    if pairs is None:
        pairs = _redaction_pairs()
    if isinstance(value, str):
        for pattern, replacement in pairs:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, dict):
        return {key: redact(item, pairs) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, pairs) for item in value]
    return value


# --------------------------------------------------------------------------- probes


def _run(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        capture_output=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
    )


def _powershell_exe() -> str:
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    candidate = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(candidate) if candidate.is_file() else "powershell.exe"


def _powershell_argv(script: str) -> list[str]:
    # -EncodedCommand sidesteps every quoting layer between Python, CreateProcess
    # and PowerShell; the XPath below does not survive plain -Command intact.
    prologue = "$ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    encoded = base64.b64encode((prologue + script).encode("utf-16-le")).decode("ascii")
    return [_powershell_exe(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]


def _stdout_text(result: subprocess.CompletedProcess) -> str:
    raw = result.stdout or b""
    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


def _stderr_tail(result: subprocess.CompletedProcess) -> str:
    raw = result.stderr or b""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    return " ".join(text.split())[-300:]


VIDEO_CONTROLLER_SCRIPT = (
    "@(Get-CimInstance Win32_VideoController | Select-Object "
    "Name,DriverVersion,DriverDate,AdapterRAM,PNPDeviceID,Status,VideoProcessor) | ConvertTo-Json -Compress"
)


def _display_events_script() -> str:
    providers = " or ".join(f"Provider[@Name='{name}']" for name in EVENT_PROVIDERS)
    window_ms = EVENT_WINDOW_DAYS * 24 * 3600 * 1000
    xpath = f"*[System[({providers}) and TimeCreated[timediff(@SystemTime) <= {window_ms}]]]"
    # Some drivers (nvlddmkm) ship no message table, so Message is empty and the
    # useful text lives in the insertion strings; binary blobs are dropped.
    return (
        f'$xp = "{xpath}"; '
        f"@(Get-WinEvent -LogName System -FilterXPath $xp -MaxEvents {EVENT_MAX_ENTRIES} -ErrorAction SilentlyContinue | "
        "ForEach-Object { $m = [string]$_.Message; "
        "if (-not $m) { $m = (@($_.Properties | Where-Object { -not ($_.Value -is [byte[]]) } | "
        "ForEach-Object { [string]$_.Value }) -join ' | ') }; "
        f"if ($m.Length -gt {EVENT_MESSAGE_CHARS}) {{ $m = $m.Substring(0, {EVENT_MESSAGE_CHARS}) }}; "
        "[pscustomobject]@{ TimeCreated = $_.TimeCreated.ToUniversalTime().ToString('o'); "
        "ProviderName = $_.ProviderName; Id = $_.Id; Level = $_.Level; "
        "LevelDisplayName = $_.LevelDisplayName; Message = $m } }) | ConvertTo-Json -Compress"
    )


def _live_kernel_events_script() -> str:
    window_ms = LIVE_KERNEL_WINDOW_DAYS * 24 * 3600 * 1000
    xpath = (
        f"*[System[Provider[@Name='{LIVE_KERNEL_PROVIDER}'] and (EventID={LIVE_KERNEL_EVENT_ID}) "
        f"and TimeCreated[timediff(@SystemTime) <= {window_ms}]]]"
    )
    # WER 1001 insertion strings: [2] event name, [5..9] P1..P5 (P1 = bugcheck-style
    # code such as 141 / 117 / 1a1 / 1b8). Filtering here rather than with an
    # EventData XPath matches on the stable insertion string AND on the message.
    return (
        f'$xp = "{xpath}"; '
        f"@(Get-WinEvent -LogName Application -FilterXPath $xp -MaxEvents {LIVE_KERNEL_SCAN_LIMIT} "
        "-ErrorAction SilentlyContinue | ForEach-Object { "
        "$d = @($_.Properties | Where-Object { -not ($_.Value -is [byte[]]) } | ForEach-Object { [string]$_.Value }); "
        "$m = [string]$_.Message; "
        "$hit = ($d -contains 'LiveKernelEvent') -or ($m -match 'LiveKernelEvent'); "
        "if ($hit) { "
        f"if ($m.Length -gt {EVENT_MESSAGE_CHARS}) {{ $m = $m.Substring(0, {EVENT_MESSAGE_CHARS}) }}; "
        "[pscustomobject]@{ TimeCreated = $_.TimeCreated.ToUniversalTime().ToString('o'); "
        "ProviderName = $_.ProviderName; Id = $_.Id; Level = $_.Level; "
        "EventName = $(if ($d.Count -gt 2) { $d[2] } else { '' }); "
        "Parameters = @($d | Select-Object -Skip 5 -First 5); Message = $m } } } "
        f"| Select-Object -First {LIVE_KERNEL_MAX_ENTRIES}) | ConvertTo-Json -Compress -Depth 3"
    )


_P1_RE = re.compile(r"\bP1:\s*([0-9A-Fa-fx]+)")


def parse_live_kernel_events(stdout: str) -> list[dict]:
    events = []
    for record in _json_records(stdout):
        message = " ".join(str(record.get("Message") or "").split())
        event_name = str(record.get("EventName") or "")
        if "LiveKernelEvent" not in event_name and "LiveKernelEvent" not in message:
            continue
        raw_params = record.get("Parameters")
        if isinstance(raw_params, str):  # a one-element array serializes as a bare string
            raw_params = [raw_params]
        parameters = [str(value)[:64] for value in (raw_params or []) if value is not None][:5]
        code = parameters[0] if parameters else ""
        if not code:
            match = _P1_RE.search(message)
            code = match.group(1) if match else ""
        level = _as_int(record.get("Level"))
        events.append(
            {
                "time": str(record.get("TimeCreated") or ""),
                "provider": str(record.get("ProviderName") or ""),
                "event_id": _as_int(record.get("Id")),
                "level": EVENT_LEVEL_NAMES.get(level, str(level or "")),
                "event_name": event_name or "LiveKernelEvent",
                "code": code.strip().lower(),
                "parameters": parameters,
                "message": message[:EVENT_MESSAGE_CHARS],
            }
        )
        if len(events) >= LIVE_KERNEL_MAX_ENTRIES:
            break
    return events


def probe_live_kernel_events(run=_run, timeout: float = PROBE_TIMEOUT_S) -> dict:
    section = {
        "log": "Application",
        "provider": LIVE_KERNEL_PROVIDER,
        "event_id": LIVE_KERNEL_EVENT_ID,
        "window_days": LIVE_KERNEL_WINDOW_DAYS,
        "max_entries": LIVE_KERNEL_MAX_ENTRIES,
        "events": [],
        "counts_by_code": {},
    }
    try:
        result = run(_powershell_argv(_live_kernel_events_script()), timeout)
        section["events"] = parse_live_kernel_events(_stdout_text(result))
        counts: dict[str, int] = {}
        for event in section["events"]:
            key = event["code"] or "unknown"
            counts[key] = counts.get(key, 0) + 1
        section["counts_by_code"] = counts
        if result.returncode != 0:
            section["error"] = f"exit {result.returncode}: {_stderr_tail(result)}"
    except subprocess.TimeoutExpired:
        section["error"] = f"timed out after {timeout:g} s"
    except Exception as exc:  # noqa: BLE001
        section["error"] = f"{type(exc).__name__}: {exc}"
    return section


def read_wer_settings(winreg_module) -> dict:
    """WER on/off: with reporting disabled Windows logs no LiveKernelEvent, so an
    empty list only means "no GPU resets" when this says reporting is enabled."""
    settings: dict = {}
    for label, path in (("disabled", WER_KEY), ("policy_disabled", WER_POLICY_KEY)):
        try:
            with winreg_module.OpenKey(winreg_module.HKEY_LOCAL_MACHINE, path) as key:
                settings[label] = _as_int(winreg_module.QueryValueEx(key, "Disabled")[0])
        except OSError:
            settings[label] = None
    return settings


def probe_video_controllers(run=_run, timeout: float = PROBE_TIMEOUT_S) -> dict:
    section = {"method": "powershell Get-CimInstance Win32_VideoController", "adapters": []}
    try:
        result = run(_powershell_argv(VIDEO_CONTROLLER_SCRIPT), timeout)
        section["adapters"] = parse_video_controllers(_stdout_text(result))
        if result.returncode != 0:
            section["error"] = f"exit {result.returncode}: {_stderr_tail(result)}"
    except subprocess.TimeoutExpired:
        section["error"] = f"timed out after {timeout:g} s"
    except Exception as exc:  # noqa: BLE001 - diagnostics must never raise
        section["error"] = f"{type(exc).__name__}: {exc}"
    return section


def probe_display_events(run=_run, timeout: float = PROBE_TIMEOUT_S) -> dict:
    section = {
        "log": "System",
        "window_days": EVENT_WINDOW_DAYS,
        "max_entries": EVENT_MAX_ENTRIES,
        "providers": list(EVENT_PROVIDERS),
        "events": [],
    }
    try:
        result = run(_powershell_argv(_display_events_script()), timeout)
        section["events"] = parse_display_events(_stdout_text(result))
        section["counts"] = summarize_events(section["events"])
        if result.returncode != 0:
            section["error"] = f"exit {result.returncode}: {_stderr_tail(result)}"
    except subprocess.TimeoutExpired:
        section["error"] = f"timed out after {timeout:g} s"
    except Exception as exc:  # noqa: BLE001
        section["error"] = f"{type(exc).__name__}: {exc}"
    return section


def _nvidia_smi_path() -> str:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    candidate = Path(root) / "System32" / "nvidia-smi.exe"
    return str(candidate) if candidate.is_file() else ""


def probe_nvidia_smi(run=_run, timeout: float = PROBE_TIMEOUT_S, exe_path: str | None = None) -> dict:
    exe = _nvidia_smi_path() if exe_path is None else exe_path
    section: dict = {"available": bool(exe), "gpus": []}
    if not exe:
        section["error"] = "nvidia-smi not found"
        return section
    argv = [exe, "--query-gpu=name,driver_version,memory.total,pstate", "--format=csv,noheader"]
    try:
        result = run(argv, timeout)
        section["gpus"] = parse_nvidia_smi(_stdout_text(result))
        if result.returncode != 0:
            section["error"] = f"exit {result.returncode}: {_stderr_tail(result) or _stdout_text(result).strip()[:300]}"
    except subprocess.TimeoutExpired:
        section["error"] = f"timed out after {timeout:g} s"
    except Exception as exc:  # noqa: BLE001
        section["error"] = f"{type(exc).__name__}: {exc}"
    return section


def _registry_int(value):
    if isinstance(value, bytes):
        return int.from_bytes(value[:8], "little") if value else None
    return _as_int(value)


def read_display_class_registry(winreg_module) -> list[dict]:
    """Per-adapter driver keys; the only stock source of 64-bit VRAM size."""
    entries = []
    with winreg_module.OpenKey(winreg_module.HKEY_LOCAL_MACHINE, DISPLAY_CLASS_KEY) as class_key:
        index = 0
        while True:
            try:
                name = winreg_module.EnumKey(class_key, index)
            except OSError:
                break
            index += 1
            if not name.isdigit():
                continue
            try:
                subkey = winreg_module.OpenKey(class_key, name)
            except OSError:
                continue
            with subkey:
                values = {}
                for value_name in (
                    "DriverDesc",
                    "DriverVersion",
                    "HardwareInformation.qwMemorySize",
                    "HardwareInformation.MemorySize",
                ):
                    try:
                        values[value_name] = winreg_module.QueryValueEx(subkey, value_name)[0]
                    except OSError:
                        pass
            if values.get("DriverDesc"):
                entries.append(
                    {
                        "key": name,
                        "driver_desc": str(values["DriverDesc"]),
                        "driver_version": str(values.get("DriverVersion") or ""),
                        "qw_memory_size": _registry_int(values.get("HardwareInformation.qwMemorySize")),
                        "memory_size": _registry_int(values.get("HardwareInformation.MemorySize")),
                    }
                )
    return entries


def merge_registry_vram(adapters: list[dict], registry_entries: list[dict]) -> None:
    """Attach ``vram_bytes`` to each CIM adapter, matched by DriverDesc (+ version)."""
    unused = list(registry_entries)
    for adapter in adapters:
        match = next(
            (
                entry
                for entry in unused
                if entry["driver_desc"] == adapter["name"]
                and (not entry["driver_version"] or entry["driver_version"] == adapter["driver_version"])
            ),
            None,
        )
        if match is None:
            match = next((entry for entry in unused if entry["driver_desc"] == adapter["name"]), None)
        if match is None:
            adapter["vram_source"] = "none"
            adapter["vram_bytes"] = None if adapter["adapter_ram_capped_32bit"] else adapter["adapter_ram_bytes"]
            continue
        unused.remove(match)
        if match["qw_memory_size"]:
            adapter["vram_bytes"] = match["qw_memory_size"]
            adapter["vram_source"] = "registry qwMemorySize"
        elif match["memory_size"]:
            adapter["vram_bytes"] = match["memory_size"]
            adapter["vram_source"] = "registry MemorySize (32-bit)"
        else:
            adapter["vram_bytes"] = None if adapter["adapter_ram_capped_32bit"] else adapter["adapter_ram_bytes"]
            adapter["vram_source"] = "none"


def read_gpu_preferences(winreg_module) -> dict:
    section: dict = {"key": "HKCU\\" + GPU_PREFERENCES_KEY, "entries": []}
    try:
        key = winreg_module.OpenKey(winreg_module.HKEY_CURRENT_USER, GPU_PREFERENCES_KEY)
    except FileNotFoundError:
        section["note"] = "key not present (no per-app GPU preferences set)"
        return section
    with key:
        index = 0
        while True:
            try:
                name, value, _kind = winreg_module.EnumValue(key, index)
            except OSError:
                break
            index += 1
            exe_name = re.split(r"[\\/]", str(name))[-1].lower()
            if exe_name in GPU_PREFERENCE_EXES:
                entry = {"exe_path": str(name)}
                entry.update(parse_gpu_preference(str(value)))
                section["entries"].append(entry)
    return section


def read_windows_version_details(winreg_module) -> dict:
    details = {}
    with winreg_module.OpenKey(winreg_module.HKEY_LOCAL_MACHINE, WINDOWS_CURRENT_VERSION_KEY) as key:
        for name in ("ProductName", "DisplayVersion", "CurrentBuild", "UBR", "EditionID"):
            try:
                details[name] = winreg_module.QueryValueEx(key, name)[0]
            except OSError:
                pass
    return details


# --------------------------------------------------------------------------- summary


def os_info(is_windows: bool) -> dict:
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    if is_windows:
        try:
            wv = sys.getwindowsversion()
            info["windows_version"] = {
                "major": wv.major,
                "minor": wv.minor,
                "build": wv.build,
                "platform": wv.platform,
                "service_pack": wv.service_pack,
            }
        except Exception as exc:  # noqa: BLE001
            info["windows_version_error"] = f"{type(exc).__name__}: {exc}"
        try:
            info["windows_edition"] = platform.win32_edition()
        except Exception:  # noqa: BLE001
            pass
    return info


def blender_version() -> str:
    try:
        import bpy  # type: ignore

        return str(getattr(getattr(bpy, "app", None), "version_string", "") or "")
    except Exception:  # noqa: BLE001 - outside Blender
        return ""


def addon_version() -> str:
    addon_dir = Path(__file__).resolve().parent
    try:
        from . import update_archive

        version = update_archive.extension_manifest_version(addon_dir)
        if version:
            return ".".join(str(part) for part in version)
    except Exception:  # noqa: BLE001
        pass
    package = sys.modules.get(__package__ or "")
    bl_info = getattr(package, "bl_info", None)
    if isinstance(bl_info, dict) and isinstance(bl_info.get("version"), (tuple, list)):
        return ".".join(str(part) for part in bl_info["version"])
    return ""


def resolve_nvidia_driver(adapters: list[dict], smi: dict) -> dict:
    derived = next(
        (adapter.get("nvidia_driver_version") for adapter in adapters if adapter.get("nvidia_driver_version")),
        "",
    )
    smi_version = next((gpu["driver_version"] for gpu in smi.get("gpus", []) if gpu.get("driver_version")), "")
    if smi_version:
        return {"version": smi_version, "method": "nvidia-smi", "derived_from_windows_driver_version": derived}
    if derived:
        return {"version": derived, "method": "windows DriverVersion", "derived_from_windows_driver_version": derived}
    return {"version": "", "method": "none", "derived_from_windows_driver_version": ""}


def _run_parallel(probes: dict, deadline_s: float) -> tuple[dict, dict]:
    results: dict = {}
    timings: dict = {}

    def worker(key, fn):
        start = time.perf_counter()
        try:
            results[key] = fn()
        except Exception as exc:  # noqa: BLE001
            results[key] = {"error": f"{type(exc).__name__}: {exc}"}
        timings[key] = round(time.perf_counter() - start, 3)

    threads = []
    for key, fn in probes.items():
        thread = threading.Thread(target=worker, args=(key, fn), name=f"fyr-sysinfo-{key}", daemon=True)
        thread.start()
        threads.append((key, thread))
    end = time.monotonic() + deadline_s
    for key, thread in threads:
        thread.join(max(0.0, end - time.monotonic()))
        if thread.is_alive():
            results.setdefault(key, {"error": f"not finished within the {deadline_s:g} s collection deadline"})
    return results, timings


def collect_system_info(
    *,
    run=_run,
    winreg_module=None,
    is_windows: bool | None = None,
    blender_version_string: str | None = None,
    addon_version_string: str | None = None,
    probe_timeout_s: float = PROBE_TIMEOUT_S,
    deadline_s: float = TOTAL_DEADLINE_S,
    nvidia_smi_path: str | None = None,
) -> dict:
    """Everything for ``system/gpu_info.json``. Never raises."""
    started = time.perf_counter()
    if is_windows is None:
        is_windows = sys.platform == "win32"
    info: dict = {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "blender_version": blender_version() if blender_version_string is None else blender_version_string,
        "addon_version": addon_version() if addon_version_string is None else addon_version_string,
    }
    try:
        info["os"] = os_info(is_windows)
    except Exception as exc:  # noqa: BLE001
        info["os"] = {"error": f"{type(exc).__name__}: {exc}"}
    if not is_windows:
        info["note"] = "GPU adapter, driver event and GPU preference probes are Windows-only."
        info["collection_seconds"] = round(time.perf_counter() - started, 3)
        return redact(info)

    if winreg_module is None:
        try:
            import winreg as winreg_module  # type: ignore
        except Exception as exc:  # noqa: BLE001
            winreg_module = None
            info["winreg_error"] = f"{type(exc).__name__}: {exc}"

    results, timings = _run_parallel(
        {
            "display_adapters": lambda: probe_video_controllers(run, probe_timeout_s),
            "display_driver_events": lambda: probe_display_events(run, probe_timeout_s),
            "nvidia_smi": lambda: probe_nvidia_smi(run, probe_timeout_s, nvidia_smi_path),
            "live_kernel_events": lambda: probe_live_kernel_events(run, probe_timeout_s),
        },
        deadline_s,
    )

    registry_entries: list[dict] = []
    if winreg_module is not None:
        for key, reader in (
            ("windows_version_details", read_windows_version_details),
            ("display_class_registry", read_display_class_registry),
            ("gpu_preferences", read_gpu_preferences),
        ):
            try:
                value = reader(winreg_module)
            except Exception as exc:  # noqa: BLE001
                value = {"error": f"{type(exc).__name__}: {exc}"}
            if key == "windows_version_details":
                info["os"]["windows_registry"] = value
            elif key == "display_class_registry":
                if isinstance(value, list):
                    registry_entries = value
                else:
                    info["display_class_registry_error"] = value["error"]
            else:
                info[key] = value

    adapters_section = results.get("display_adapters") or {}
    adapters = adapters_section.get("adapters") or []
    try:
        merge_registry_vram(adapters, registry_entries)
    except Exception as exc:  # noqa: BLE001
        adapters_section["vram_merge_error"] = f"{type(exc).__name__}: {exc}"
    info["display_adapters"] = adapters_section
    smi = results.get("nvidia_smi") or {}
    info["nvidia_smi"] = smi
    info["nvidia_driver"] = resolve_nvidia_driver(adapters, smi)
    info["display_driver_events"] = results.get("display_driver_events") or {}
    live_kernel = results.get("live_kernel_events") or {}
    if winreg_module is not None:
        try:
            live_kernel["wer_settings"] = read_wer_settings(winreg_module)
        except Exception as exc:  # noqa: BLE001
            live_kernel["wer_settings"] = {"error": f"{type(exc).__name__}: {exc}"}
        wer = live_kernel["wer_settings"]
        if wer.get("disabled") == 1 or wer.get("policy_disabled") == 1:
            live_kernel["note"] = (
                "Windows Error Reporting is disabled on this machine, so no LiveKernelEvent "
                "entries are logged; an empty list does not rule out GPU resets."
            )
    info["live_kernel_events"] = live_kernel
    info["probe_seconds"] = timings
    info["collection_seconds"] = round(time.perf_counter() - started, 3)
    return redact(info)
