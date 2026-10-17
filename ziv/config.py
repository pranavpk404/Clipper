"""Configuration loaded from environment / .env file."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def _dotenv_value(raw: str) -> str:
    """Strip whitespace-delimited comments while preserving quoted/hash values."""
    quote = ""
    escaped = False
    for index, char in enumerate(raw):
        if char == "#" and not quote and (index == 0 or raw[index - 1].isspace()):
            raw = raw[:index]
            break
        if char in {"'", '"'} and not escaped:
            if quote == char:
                quote = ""
            elif not quote:
                quote = char
        escaped = char == "\\" and not escaped
    value = raw.strip()
    if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
        value = value[1:-1]
    return value


def _load_dotenv() -> None:
    """Tiny .env loader (avoids extra dependency)."""
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = _dotenv_value(value)
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# --- Gemini ---------------------------------------------------------------
# NOTE on free-tier limits: Google no longer publishes fixed RPM/RPD tables —
# live numbers are per project and visible in AI Studio. Quotas reset at
# midnight Pacific time. What IS stable: limits are PER MODEL, so rotation
# below gives each model its own fresh bucket.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

# Runtime model rotation: free-tier limits are PER MODEL, so when the primary
# model hits 429/quota (or 503 overload) mid-run, gemini.py switches to the
# next model here and continues (sticky for the rest of the run). Models
# retired by Google (404) are skipped automatically.
#
# Default chain verified live against the API (Sep 2026):
#   gemini-3.8-flash      primary — newest Flash; free tier, busiest at peaks
#   gemini-2.5-flash      working, own quota bucket
#   gemini-3.1-flash-lite working, lite tier (typically the roomiest limits)
#   gemini-flash-latest   alias -> newest Flash; tracks future releases
# (gemini-2.0-flash was retired by Google — do not put it back.)
# Empty = no rotation.
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get(
        "GEMINI_MODEL_FALLBACKS",
        "gemini-2.5-flash,gemini-3.1-flash-lite,gemini-flash-latest").split(",")
    if m.strip() and m.strip().lower() != GEMINI_MODEL.lower()
]
try:
    GEMINI_MIN_INTERVAL = max(0.0, float(os.environ.get("GEMINI_MIN_INTERVAL_SECONDS", "20")))
except ValueError:
    GEMINI_MIN_INTERVAL = 20.0
try:
    GEMINI_SELECTION_CHUNK_CHARS = max(
        4000, int(os.environ.get("GEMINI_SELECTION_CHUNK_CHARS", "18000")))
except ValueError:
    GEMINI_SELECTION_CHUNK_CHARS = 18000

# --- Local analysis budget --------------------------------------------------
# Visual fallback analysis is intentionally sparse. Keeping this bounded makes
# a retry cheap on small machines while still giving Gemini useful coverage.
try:
    ANALYSIS_MAX_FRAMES = max(4, min(32, int(
        os.environ.get("ANALYSIS_MAX_FRAMES", "12"))))
except ValueError:
    ANALYSIS_MAX_FRAMES = 12

# --- Instagram ------------------------------------------------------------
IG_USERNAME = os.environ.get("IG_USERNAME", "")
IG_PASSWORD = os.environ.get("IG_PASSWORD", "")
IG_2FA_CODE = os.environ.get("IG_2FA_CODE", "")

# --- Output ---------------------------------------------------------------
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", PROJECT_ROOT / "output"))
SESSION_FILE = Path(
    os.environ.get("IG_SESSION_FILE", PROJECT_ROOT / ".ig_session"))
LINKS_FILE = Path(os.environ.get("LINKS_FILE", PROJECT_ROOT / "links.txt"))
CHANNELS_FILE = Path(os.environ.get("CHANNELS_FILE", PROJECT_ROOT / "channels.txt"))
CHANNEL_BACKLOG_MAX = int(os.environ.get("CHANNEL_BACKLOG_MAX", "20"))
CHANNEL_SCAN_MAX = int(os.environ.get("CHANNEL_SCAN_MAX", "0"))

# --- Reels constraints (Instagram limits) ---------------------------------
REELS_MAX_DURATION = 90          # seconds
REELS_ASPECT = (9, 16)           # width : height
CLIP_WIDTH = 1080
CLIP_HEIGHT = 1920
TARGET_FPS = 30

# --- Source quality (adaptive) ----------------------------------------------
# Clips are ALWAYS rendered at 1080x1920. These caps control the quality of
# the downloaded master before the vertical crop. A landscape 1080p source
# only contributes about 608 horizontal pixels to a 9:16 crop, so the default
# highest profile keeps more source detail: 1440p for long videos and up to
# 2160p for short ones. Set SOURCE_MAX_HEIGHT to pin one cap for everything.
_QUALITY_MODE = os.environ.get("QUALITY", "highest").strip().lower()
_PINNED_HEIGHT = os.environ.get("SOURCE_MAX_HEIGHT", "").strip()
SOURCE_LONG_THRESHOLD_MINUTES = float(
    os.environ.get("SOURCE_LONG_THRESHOLD_MINUTES", "10"))
if _PINNED_HEIGHT:
    SOURCE_MAX_HEIGHT_LONG = int(_PINNED_HEIGHT)
    SOURCE_MAX_HEIGHT_SHORT = int(_PINNED_HEIGHT)
elif _QUALITY_MODE in {"highest", "maximum", "max"}:
    SOURCE_MAX_HEIGHT_LONG = int(os.environ.get("SOURCE_MAX_HEIGHT_LONG", "1440"))
    SOURCE_MAX_HEIGHT_SHORT = int(os.environ.get("SOURCE_MAX_HEIGHT_SHORT", "2160"))
elif _QUALITY_MODE == "high":
    SOURCE_MAX_HEIGHT_LONG = int(os.environ.get("SOURCE_MAX_HEIGHT_LONG", "1080"))
    SOURCE_MAX_HEIGHT_SHORT = int(os.environ.get("SOURCE_MAX_HEIGHT_SHORT", "1440"))
else:
    SOURCE_MAX_HEIGHT_LONG = int(os.environ.get("SOURCE_MAX_HEIGHT_LONG", "720"))
    SOURCE_MAX_HEIGHT_SHORT = int(os.environ.get("SOURCE_MAX_HEIGHT_SHORT", "1080"))
SOURCE_LONG_SECONDS = SOURCE_LONG_THRESHOLD_MINUTES * 60.0

# --- Posting window ----------------------------------------------------------
# Only post between these local hours. Default 17-0 = 5pm-midnight IST: every
# India-audience study puts the peak at 6-10pm, 7-9pm sharpest. Overnight
# ranges wrap ("22-2"). Empty string = post any time.
POST_HOURS = os.environ.get("POST_HOURS", "17-0")

# --- Instagram posting queue (links.txt -> scheduled posting) -------------
def _env_minutes(key: str, default_minutes: float) -> float:
    try:
        return float(os.environ.get(key, default_minutes)) * 60
    except ValueError:
        return default_minutes * 60


QUEUE_MIN_GAP = _env_minutes("QUEUE_MIN_GAP_MINUTES", 60)    # min seconds between posts
QUEUE_MAX_GAP = _env_minutes("QUEUE_MAX_GAP_MINUTES", 120)   # upper bound (randomized)
QUEUE_MAX_ATTEMPTS = int(os.environ.get("QUEUE_MAX_ATTEMPTS", "3"))


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# --- Lean output and cleanup -------------------------------------------------
# Source captions are used whenever available; Whisper remains the fallback
# for sources without a usable timestamped caption track.
SUBTITLE_SOURCE = os.environ.get("SUBTITLE_SOURCE", "auto").strip().lower()
SUB_STYLE = os.environ.get("SUB_STYLE", "hormozi").strip().lower()
SUB_LANG = os.environ.get("SUB_LANG", "").strip() or None
MAKE_COVERS = _env_bool("MAKE_COVERS", False)
AUDIO_NORMALIZATION = _env_bool("AUDIO_NORMALIZATION", True)
AUTO_CLIP_MODE = os.environ.get("AUTO_CLIP_MODE", "content").strip().lower()

# These are intentionally enabled for the user's disposable-media workflow.
# Queue history and manifests are always retained; only confirmed media files
# are eligible for removal.
DELETE_SOURCE_AFTER_CLIP = _env_bool("DELETE_SOURCE_AFTER_CLIP", False)
DELETE_POSTED_CLIPS = _env_bool("DELETE_POSTED_CLIPS", False)
