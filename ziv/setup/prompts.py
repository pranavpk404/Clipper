"""Small injectable prompt helpers used by the interactive setup wizard."""
from __future__ import annotations

import getpass
from collections.abc import Callable, Sequence


class SetupInteractionError(RuntimeError):
    """Interactive setup could not collect an answer."""


class PromptSession:
    """Prompt session with hidden-input support and test-friendly callables."""

    def __init__(
        self,
        input_fn: Callable[[str], str] | None = None,
        secret_fn: Callable[[str], str] | None = None,
    ) -> None:
        self.input_fn = input if input_fn is None else input_fn
        self.secret_fn = getpass.getpass if secret_fn is None else secret_fn

    def _read(self, prompt: str, *, secret: bool = False) -> str:
        try:
            return (self.secret_fn if secret else self.input_fn)(prompt)
        except (EOFError, KeyboardInterrupt) as exc:
            raise SetupInteractionError("Setup input was interrupted") from exc

    def text(self, label: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        answer = self._read(f"{label}{suffix}: ").strip()
        return answer if answer else default

    def secret(self, label: str, default: str = "") -> str:
        hint = " [leave blank to keep current]" if default else ""
        answer = self._read(f"{label}{hint}: ", secret=True).strip()
        return answer if answer else default

    def choice(self, label: str, choices: Sequence[str], default: str) -> str:
        options = "/".join(choices)
        while True:
            answer = self.text(f"{label} ({options})", default).lower()
            if answer in choices:
                return answer
            print(f"Please choose one of: {', '.join(choices)}")

    def boolean(self, label: str, default: bool) -> bool:
        default_text = "Y/n" if default else "y/N"
        while True:
            answer = self._read(f"{label} [{default_text}]: ").strip().lower()
            if not answer:
                return default
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False
            print("Please answer yes or no.")


__all__ = ["PromptSession", "SetupInteractionError"]
