"""Offline contract tests for opt-in pipeline profiling."""
from __future__ import annotations

import json
from pathlib import Path

from ziv.core import profiling
from ziv.setup import profiler as system_profiler


def test_disabled_profile_is_a_noop(tmp_path: Path, monkeypatch) -> None:
    writes: list[Path] = []
    monkeypatch.setattr(
        profiling,
        "atomic_json",
        lambda path, data: writes.append(path),
    )

    profile = profiling.PipelineProfile(enabled=False)
    with profile.stage("offline-stage"):
        pass
    profile.count("cache-hit", 3)
    profile.save(tmp_path / "profile.json")

    assert profile.data == {"version": 1, "stages": {}, "counters": {}}
    assert writes == []


def test_enabled_profile_records_stage_duration_and_counters(
    monkeypatch,
) -> None:
    clock = iter((10.0, 10.125))
    monkeypatch.setattr(profiling.time, "perf_counter", lambda: next(clock))

    profile = profiling.PipelineProfile(enabled=True)
    with profile.stage("offline-stage"):
        pass
    profile.count("cache-hit")
    profile.count("cache-hit", 2)

    assert profile.data["stages"] == {"offline-stage": 0.125}
    assert profile.data["counters"] == {"cache-hit": 3}


def test_enabled_profile_persists_json_without_external_services(tmp_path: Path) -> None:
    output = tmp_path / "profile.json"
    profile = profiling.PipelineProfile(enabled=True)
    profile.count("synthetic", 2)

    profile.save(output)

    assert json.loads(output.read_text(encoding="utf-8")) == profile.data
    assert output.parent == tmp_path


def test_system_profiler_uses_mocked_local_capabilities_only(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(system_profiler.platform, "system", lambda: "Linux")
    monkeypatch.setattr(system_profiler.platform, "release", lambda: "synthetic")
    monkeypatch.setattr(system_profiler.platform, "machine", lambda: "synthetic-x86")
    monkeypatch.setattr(system_profiler, "_linux_distro", lambda: "Synthetic Linux")
    monkeypatch.setattr(system_profiler, "_cpu_threads", lambda: 4)
    monkeypatch.setattr(system_profiler, "_read_ram", lambda system: 8 * 1024**3)
    monkeypatch.setattr(system_profiler.shutil, "which", lambda name: {
        "ffmpeg": "/synthetic/bin/ffmpeg",
        "ffprobe": "/synthetic/bin/ffprobe",
        "lspci": "/synthetic/bin/lspci",
    }.get(name))

    def fake_run(command: list[str], timeout: float = 2.0) -> str:
        commands.append(command)
        if command[-1] == "-version":
            return "synthetic tool version\n"
        if command[0].endswith("lspci"):
            return "00:02.0 VGA compatible controller: Synthetic GPU\n"
        if command[-1] == "-hwaccels":
            return "Hardware acceleration methods:\nvaapi\nvulkan\n"
        return ""

    monkeypatch.setattr(system_profiler, "_run", fake_run)

    profile = system_profiler.collect_system_profile()

    assert profile.os_name == "Linux"
    assert profile.distro == "Synthetic Linux"
    assert profile.cpu_threads == 4
    assert profile.ram_gb == 8.0
    assert profile.gpu_hints == ("Synthetic GPU",)
    assert profile.hardware_acceleration == ("vaapi", "vulkan")
    assert profile.ffmpeg.path == "/synthetic/bin/ffmpeg"
    assert all(command[0] != "sh" for command in commands)
    assert all("network" not in command for command in commands)
    assert profile.to_dict()["gpu_hints"] == ["Synthetic GPU"]
