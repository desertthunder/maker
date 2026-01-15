import hashlib
import json
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class Color(str, Enum):
    SUCCESS = "\033[92m"
    ERROR = "\033[91m"
    INFO = "\033[94m"
    WARNING = "\033[93m"
    RESET = "\033[0m"


class Format(str, Enum):
    MP4 = "mp4"
    MKV = "mkv"
    WEBM = "webm"
    GIF = "gif"
    M4A = "m4a"
    WAV = "wav"
    MP3 = "mp3"


def colored(text: str, color: Color) -> str:
    return f"{color.value}{text}{Color.RESET.value}"


def echo(text: str, color: Color = Color.INFO) -> None:
    print(colored(text, color))


class InvalidPaperSizeError(ValueError):
    def __init__(self, size_str: str):
        super().__init__(
            f"Invalid paper size: {size_str}. Valid sizes: {[s.name for s in PaperSize]}"
        )


class NotADirectoryError(ValueError):
    def __init__(self, path: str):
        super().__init__(f"Not a directory: {path}")


class ProcessingError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class InvalidInputError(Exception):
    def __init__(self, input: str):
        super().__init__(f"Invalid input: {input}")


class FFmpegNotFoundError(Exception):
    def __init__(self):
        super().__init__(
            "FFmpeg binary not found. Install FFmpeg or run: pip install imageio-ffmpeg"
        )

class FFmpegError(Exception):
    def __init__(self, stderr: any):
        super().__init__(f"FFmpeg error: {stderr}")


class InvalidTimeFormatError(ValueError):
    def __init__(self, time_str: str):
        super().__init__(
            f"Invalid time format: {time_str}. Use HH:MM:SS.mmm, HH:MM:SS, or seconds as float"
        )


class NoAudioStreamError(Exception):
    def __init__(self, source_path: str):
        super().__init__(f"No audio stream found in: {source_path}")


class FileAlreadyExistsError(Exception):
    def __init__(self, path: str):
        super().__init__(f"File already exists: {path}. Use --overwrite to replace")


class AliasNotFoundError(Exception):
    def __init__(self, alias: str):
        super().__init__(f"Downloaded video alias not found: {alias}")


class TimeRangeError(ValueError):
    def __init__(self, start: float, end: float, duration: float | None = None):
        msg = f"Invalid time range: start ({start}) must be less than end ({end})"
        if duration is not None:
            msg += f" and within video duration ({duration})"
        super().__init__(msg)


class PaperSize(Enum):
    A0 = (2384, 3370)
    A1 = (1684, 2384)
    A2 = (1191, 1684)
    A3 = (842, 1191)
    A4 = (595, 842)
    A5 = (420, 595)
    A6 = (298, 420)
    A7 = (210, 298)
    A8 = (147, 210)
    A9 = (105, 147)
    A10 = (74, 105)
    B0 = (2835, 4008)
    B1 = (2004, 2835)
    B2 = (1417, 2004)
    B3 = (1001, 1417)
    B4 = (709, 1001)
    B5 = (499, 709)
    B6 = (354, 499)
    B7 = (249, 354)
    B8 = (176, 249)
    B9 = (125, 176)
    B10 = (88, 125)

    @property
    def width(self) -> int:
        return self.value[0]

    @property
    def height(self) -> int:
        return self.value[1]

    @staticmethod
    def from_string(size_str: str) -> "PaperSize":
        try:
            return PaperSize[size_str.upper()]
        except KeyError as exc:
            raise InvalidPaperSizeError(size_str) from exc


def parse_time(time_str: str) -> float:
    """Parse time string to seconds.

    Supports:
    - HH:MM:SS.mmm
    - HH:MM:SS
    - Seconds as float (e.g., "83.42")

    Returns:
        float: Time in seconds
    """
    try:
        return float(time_str)
    except ValueError:
        pass

    parts = time_str.strip().split(":")
    if len(parts) == 3:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            sec_parts = parts[2].split(".")
            seconds = int(sec_parts[0])
            millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
            return hours * 3600 + minutes * 60 + seconds + millis / 1000
        except (ValueError, IndexError):
            pass
    elif len(parts) == 2:
        try:
            minutes = int(parts[0])
            sec_parts = parts[1].split(".")
            seconds = int(sec_parts[0])
            millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
            return minutes * 60 + seconds + millis / 1000
        except (ValueError, IndexError):
            pass

    raise InvalidTimeFormatError(time_str)


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm string."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def sanitize_filename(name: str) -> str:
    """Sanitize a string for safe use as a filename."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()


def compute_file_hash(path: str, algorithm: str = "sha256") -> str:
    """Compute hash of a file."""
    hash_func = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def parse_range(start: str, end: str) -> tuple[float, float]:
    start = parse_time(start)
    end = parse_time(end)
    if start >= end:
        raise TimeRangeError(start, end)
    return start, end


@dataclass
class DownloadSpec:
    """Specification for a downloaded video."""

    source_url: str
    video_id: str
    alias: str
    downloaded_files: list[dict]
    yt_dlp_opts: dict
    created_at: str
    title: str
    duration: float


@dataclass
class ClipSpec:
    """Specification for a generated clip."""

    artifact_path: str
    start: float
    end: float
    format: str
    ffmpeg_params: dict
    derived_from: str
    source_hash: str
    created_at: str


@dataclass
class AudioSpec:
    """Specification for a generated audio clip."""

    artifact_path: str
    start: float
    end: float
    format: str
    ffmpeg_params: dict
    derived_from: str
    source_hash: str
    created_at: str


class ManifestManager:
    """Manager for reading and writing manifest files."""

    @staticmethod
    def write_download_manifest(
        alias: str, spec: DownloadSpec, downloads_dir: Path
    ) -> None:
        """Write manifest for a downloaded video."""
        manifest_dir = downloads_dir / alias
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / "manifest.json"

        with open(manifest_path, "w") as f:
            json.dump(asdict(spec), f, indent=2)

    @staticmethod
    def read_download_manifest(alias: str, downloads_dir: Path) -> DownloadSpec:
        """Read manifest for a downloaded video."""
        manifest_path = downloads_dir / alias / "manifest.json"
        if not manifest_path.exists():
            raise AliasNotFoundError(alias)

        with open(manifest_path) as f:
            data = json.load(f)

        return DownloadSpec(**data)

    @staticmethod
    def append_artifact_record(
        spec: ClipSpec | AudioSpec, artifacts_file: Path
    ) -> None:
        """Append artifact record to JSONL file."""
        artifacts_file.parent.mkdir(parents=True, exist_ok=True)

        with open(artifacts_file, "a") as f:
            f.write(json.dumps(asdict(spec)) + "\n")

    @staticmethod
    def list_downloads(downloads_dir: Path) -> dict[str, DownloadSpec]:
        """List all downloaded videos by alias."""
        downloads = {}
        for manifest_path in downloads_dir.glob("*/manifest.json"):
            alias = manifest_path.parent.name
            with open(manifest_path) as f:
                data = json.load(f)
            downloads[alias] = DownloadSpec(**data)
        return downloads
