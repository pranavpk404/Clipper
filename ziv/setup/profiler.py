"""Safe, dependency-free system discovery used by ``ziv setup``.

The profiler is deliberately conservative.  It only invokes fixed, read-only
commands when they are present, never assumes a package manager or a GPU, and
returns an empty hint when a platform does not expose a capability.
"""
from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolInfo:
    """Availability and version information for one local command."""

    available: bool
    path: str | None = None
    version: str | None = None


@dataclass(frozen=True)
class SystemProfile:
    """A JSON-safe snapshot of the hardware/software relevant to Ziv."""

    os_name: str
    distro: str
    release: str
    machine: str
    cpu_threads: int
    ram_bytes: int | None
    gpu_hints: tuple[str, ...]
    ffmpeg: ToolInfo
    ffprobe: ToolInfo
    hardware_acceleration: tuple[str, ...]

    @property
    def ram_gb(self) -> float | None:
        if self.ram_bytes is None:
            return None
        return round(self.ram_bytes / (1024 ** 3), 1)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation for diagnostics and callers."""
        value = asdict(self)
        value["gpu_hints"] = list(self.gpu_hints)
        value["hardware_acceleration"] = list(self.hardware_acceleration)
        value["ram_gb"] = self.ram_gb
        return value


def _run(command: list[str], timeout: float = 2.0) -> str:
    """Run a fixed diagnostic command without invoking a shell."""
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    # FFmpeg and several platform diagnostics write status to stderr even on
    # success; combining both streams keeps detection portable and read-only.
    return (result.stdout or "") + (result.stderr or "")


def _tool_info(name: str) -> ToolInfo:
    path = shutil.which(name)
    if not path:
        return ToolInfo(False)
    output = _run([path, "-version"])
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    # Keep the diagnostic compact and avoid exposing arbitrary command output.
    version = first_line[:180] or None
    return ToolInfo(True, path, version)


def _read_linux_ram() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemTotal:"):
                match = re.search(r"(\d+)", line)
                if match:
                    return int(match.group(1)) * 1024
    except (OSError, UnicodeError, ValueError):
        return None
    return None


def _read_windows_ram() -> int | None:
    try:
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total_physical)
    except (AttributeError, OSError, TypeError):
        return None
    return None


def _read_ram(system: str) -> int | None:
    if system == "Linux":
        value = _read_linux_ram()
        if value is not None:
            return value
    if system == "Windows":
        value = _read_windows_ram()
        if value is not None:
            return value
    if system == "Darwin":
        output = _run(["sysctl", "-n", "hw.memsize"])
        try:
            return int(output.strip())
        except ValueError:
            pass
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page_size)
    except (AttributeError, OSError, ValueError):
        return None


def _linux_distro() -> str:
    try:
        values: dict[str, str] = {}
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip().strip('"')
        return values.get("PRETTY_NAME") or values.get("NAME") or "Linux"
    except (OSError, UnicodeError):
        return "Linux"


def _cpu_threads() -> int:
    try:
        affinity = os.sched_getaffinity(0)
        if affinity:
            return max(1, len(affinity))
    except (AttributeError, OSError):
        pass
    return max(1, os.cpu_count() or 1)


def _gpu_hints(system: str) -> tuple[str, ...]:
    """Collect human-readable GPU hints without opening driver databases."""
    hints: list[str] = []

    if shutil.which("nvidia-smi"):
        output = _run([
            "nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits",
        ])
        hints.extend(line.strip() for line in output.splitlines() if line.strip())

    if shutil.which("rocm-smi"):
        output = _run(["rocm-smi", "--showproductname", "--csv"])
        for line in output.splitlines():
            line = line.strip()
            if line and line not in hints:
                hints.append(line[:180])

    if system == "Darwin" and shutil.which("system_profiler"):
        output = _run(["system_profiler", "SPDisplaysDataType", "-detailLevel", "mini"])
        for line in output.splitlines():
            line = line.strip()
            if line and ("Chipset Model:" in line or "Graphics/Displays:" in line):
                value = line.split(":", 1)[-1].strip()
                if value:
                    hints.append(value[:180])

    if system == "Linux" and shutil.which("lspci"):
        output = _run(["lspci", "-nn"])
        for line in output.splitlines():
            if re.search(r"\b(vga(?:\s+compatible)?|3d|display)\s+controller\b",
                         line, re.IGNORECASE):
                value = line.split(": ", 1)[-1].strip()
                if value:
                    hints.append(value[:180])

    if system == "Windows" and shutil.which("powershell"):
        output = _run([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
        ])
        hints.extend(line.strip()[:180] for line in output.splitlines() if line.strip())

    unique: list[str] = []
    for hint in hints:
        if hint not in unique:
            unique.append(hint)
    return tuple(unique)


def _hardware_acceleration(ffmpeg: ToolInfo) -> tuple[str, ...]:
    if not ffmpeg.available or not ffmpeg.path:
        return ()
    output = _run([ffmpeg.path, "-hide_banner", "-hwaccels"], timeout=3.0)
    methods: list[str] = []
    started = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("hardware acceleration methods"):
            started = True
            continue
        if started and stripped and not stripped.endswith(":"):
            methods.append(stripped)
    return tuple(dict.fromkeys(methods))


def collect_system_profile() -> SystemProfile:
    """Probe local capabilities and return a safe, best-effort snapshot."""
    system = platform.system() or "Unknown"
    if system == "Linux":
        distro = _linux_distro()
    elif system == "Darwin":
        distro = "macOS"
    elif system == "Windows":
        distro = "Windows"
    else:
        distro = system
    ffmpeg = _tool_info("ffmpeg")
    ffprobe = _tool_info("ffprobe")
    return SystemProfile(
        os_name=system,
        distro=distro,
        release=platform.release() or "unknown",
        machine=platform.machine() or "unknown",
        cpu_threads=_cpu_threads(),
        ram_bytes=_read_ram(system),
        gpu_hints=_gpu_hints(system),
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        hardware_acceleration=_hardware_acceleration(ffmpeg),
    )


# Short aliases make the profiler convenient to consume from scripts.
profile_system = collect_system_profile
SystemProfiler = SystemProfile


__all__ = [
    "SystemProfile", "SystemProfiler", "ToolInfo", "collect_system_profile",
    "profile_system",
]
