"""Offline tests for YouTube doctor diagnostics and probe boundaries."""
from __future__ import annotations

from collections.abc import Mapping

from ziv import cli
from ziv import doctor
from ziv.core import downloader


def test_doctor_without_url_reports_local_auth_status_only(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        downloader,
        "youtube_auth_status",
        lambda: {
            "ok": True,
            "method": "anonymous",
            "message": "synthetic local status",
        },
    )

    def unexpected_probe(url: str) -> bool:
        raise AssertionError(f"doctor tried to probe {url!r}")

    monkeypatch.setattr(downloader, "check_youtube_access", unexpected_probe)

    assert cli._doctor(["youtube"]) == 0
    output = capsys.readouterr().out
    assert "[youtube] method: anonymous" in output
    assert "synthetic local status" in output


def test_doctor_invalid_local_auth_skips_network_probe(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        downloader,
        "youtube_auth_status",
        lambda: {
            "ok": False,
            "method": "invalid",
            "message": "synthetic invalid configuration",
        },
    )

    def unexpected_probe(url: str) -> bool:
        raise AssertionError(f"doctor tried to probe {url!r}")

    monkeypatch.setattr(downloader, "check_youtube_access", unexpected_probe)

    assert cli._doctor(["youtube", "offline://video"]) == 2
    output = capsys.readouterr().out
    assert "[youtube] method: invalid" in output
    assert "synthetic invalid configuration" in output


def test_doctor_passes_a_synthetic_url_to_the_mocked_probe(monkeypatch, capsys) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        downloader,
        "youtube_auth_status",
        lambda: {
            "ok": True,
            "method": "browser",
            "message": "synthetic browser metadata only",
        },
    )

    def fake_probe(url: str) -> bool:
        seen.append(url)
        return True

    monkeypatch.setattr(downloader, "check_youtube_access", fake_probe)

    assert cli._doctor(["youtube", "offline://video"]) is True
    assert seen == ["offline://video"]
    assert "synthetic browser metadata only" in capsys.readouterr().out


def test_auth_status_validates_metadata_without_reading_cookie_contents(
    tmp_path, monkeypatch
) -> None:
    cookie_file = tmp_path / "synthetic-cookies.txt"
    cookie_file.write_text("synthetic placeholder; not a credential\n", encoding="utf-8")
    env: Mapping[str, str] = {"YTDLP_COOKIES_FILE": str(cookie_file)}

    status = downloader.youtube_auth_status(env)

    assert status["ok"] is True
    assert status["method"] == "file"
    assert "contents were not inspected" in status["message"]


def test_doctor_help_is_local_and_does_not_probe(capsys) -> None:
    assert cli._doctor(["--help"]) == 0
    output = capsys.readouterr().out
    assert "Usage: ziv doctor [dependencies|youtube [URL]]" in output


def test_dependency_doctor_renders_mocked_local_checks(monkeypatch, capsys) -> None:
    platform = doctor.PlatformInfo(
        family="synthetic",
        label="Synthetic test host",
        hints=("install hint shown only",),
    )
    checks = [
        doctor.Check("synthetic-required", True, "available"),
        doctor.Check("synthetic-optional", False, "not configured", required=False),
    ]
    monkeypatch.setattr(doctor, "detect_platform", lambda: platform)
    monkeypatch.setattr(doctor, "dependency_checks", lambda: checks)

    assert doctor.run_doctor() == 0
    output = capsys.readouterr().out
    assert "Synthetic test host [synthetic]" in output
    assert "PASS synthetic-required" in output
    assert "WARN synthetic-optional" in output
    assert "install hint shown only" in output
