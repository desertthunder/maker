import platform
import shutil
from datetime import datetime
from pathlib import Path

import ffmpeg

from maker.shared import (
    ClipSpec,
    AudioSpec,
    ManifestManager,
    compute_file_hash,
    format_time,
    Format,
    Color,
    echo,
    FFmpegNotFoundError,
    NoAudioStreamError,
    FileAlreadyExistsError,
    FFmpegError,
)

IS_MACOS = platform.system() == "Darwin"


class UnsupportedFormatError(Exception):
    """Unsupported format error."""

    def __init__(self, fmt: str | Format):
        super().__init__(f"Unsupported format: {fmt}. Supported: {Cutter.SUPPORTED_VIDEO_FORMATS}")


class Cutter:
    """Frame-accurate video and audio cutter using ffmpeg-python."""

    DEFAULT_OUTPUT_DIR = Path("clips")
    DEFAULT_AUDIO_DIR = Path("audio")

    SUPPORTED_VIDEO_FORMATS = {Format.MP4, Format.MKV, Format.WEBM, Format.GIF}
    SUPPORTED_AUDIO_FORMATS = {Format.M4A, Format.WAV, Format.MP3}

    def __init__(
        self,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        audio_dir: Path | str = DEFAULT_AUDIO_DIR,
        ffmpeg_bin: str | None = None,
        verbose: bool = False,
        overwrite: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.audio_dir = Path(audio_dir)
        self.ffmpeg_bin = ffmpeg_bin
        self.verbose = verbose
        self.overwrite = overwrite

        self._ensure_ffmpeg()

    def _ensure_ffmpeg(self) -> None:
        if self.ffmpeg_bin:
            if not Path(self.ffmpeg_bin).exists():
                raise FFmpegNotFoundError()

            ffmpeg_path = shutil.which(self.ffmpeg_bin)
            if ffmpeg_path:
                ffmpeg.get_bin_path = lambda: ffmpeg_path
            return

        try:
            import imageio_ffmpeg

            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg.get_bin_path = lambda: ffmpeg_path
        except ImportError as exc:
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                raise FFmpegNotFoundError() from exc

    def _get_output_path(
        self,
        source_path: Path,
        start: float,
        end: float,
        fmt: str | Format,
        output_dir: Path,
    ) -> Path:
        stem = source_path.stem
        time_suffix = (
            f"{format_time(start).replace(':', '-')}_to_{format_time(end).replace(':', '-')}"
        )
        filename = f"{stem}_{time_suffix}.{fmt}"
        return output_dir / filename

    def _probe_audio(self, path: Path) -> bool:
        try:
            probe = ffmpeg.probe(str(path))
            return any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        except ffmpeg.Error:
            return False

    def _check_overwrite(self, path: Path, overwrite: bool) -> None:
        if path.exists() and not overwrite:
            raise FileAlreadyExistsError(str(path))

    def clip(
        self,
        source_path: Path,
        start: float,
        end: float,
        fmt: str | Format,
        output_dir: Path | None = None,
        overwrite: bool = False,
        allow_no_audio: bool = False,
    ) -> ClipSpec:
        """Create a frame-accurate video clip.

        Args:
            source_path: Path to source video
            start: Start time in seconds
            end: End time in seconds
            fmt: Output format (mp4, mkv, webm, gif)
            output_dir: Output directory (defaults to self.output_dir)
            overwrite: Whether to overwrite existing files
            allow_no_audio: Whether to allow video-only output

        Returns:
            ClipSpec with clip metadata
        """
        if fmt not in self.SUPPORTED_VIDEO_FORMATS:
            raise UnsupportedFormatError(fmt)

        if output_dir is None:
            output_dir = self.output_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = self._get_output_path(source_path, start, end, fmt, output_dir)

        if output_path.exists() and not overwrite:
            raise FileAlreadyExistsError(str(output_path))

        source_hash = compute_file_hash(str(source_path))
        created_at = datetime.now().isoformat()

        echo(f"Creating {fmt.upper()} clip: {output_path.name}", Color.INFO)

        if fmt == Format.GIF:
            self._create_gif(source_path, start, end, output_path)
        else:
            self._create_video_clip(source_path, start, end, fmt, output_path, allow_no_audio)

        spec = ClipSpec(
            artifact_path=str(output_path),
            start=start,
            end=end,
            format=fmt,
            ffmpeg_params=self._get_ffmpeg_params(fmt),
            derived_from=str(source_path),
            source_hash=source_hash,
            created_at=created_at,
        )

        artifacts_file = output_dir / "artifacts.jsonl"
        ManifestManager.append_artifact_record(spec, artifacts_file)

        echo(f"Clip created: {output_path}", Color.SUCCESS)
        return spec

    def _create_video_clip(
        self,
        source_path: Path,
        start: float,
        end: float,
        fmt: str | Format,
        output_path: Path,
        allow_no_audio: bool,
    ) -> None:
        has_audio = self._probe_audio(source_path)

        if not has_audio and not allow_no_audio:
            raise NoAudioStreamError(str(source_path))

        inp = ffmpeg.input(str(source_path))
        video = inp.video.filter("trim", start=start, end=end).filter("setpts", "PTS-STARTPTS")

        if has_audio:
            audio = inp.audio.filter("atrim", start=start, end=end).filter(
                "asetpts", "PTS-STARTPTS"
            )
            streams = [video, audio]
        else:
            streams = [video]

        output_kwargs = self._get_output_kwargs(fmt)
        out = ffmpeg.output(*streams, str(output_path), **output_kwargs).overwrite_output()

        cmd = out.compile()

        probe = ffmpeg.probe(str(source_path))
        video_codec = None
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                video_codec = stream.get("codec_name")
                break

        try:
            input_index = next(i for i, arg in enumerate(cmd) if arg == "-i")
            if video_codec == "av1" and IS_MACOS:
                cmd.insert(input_index, "none")
                cmd.insert(input_index, "-hwaccel")
        except StopIteration:
            pass

        try:
            if self.verbose:
                print(f"Running: {' '.join(cmd)}")
            import subprocess

            subprocess.run(cmd, check=True, capture_output=not self.verbose)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8") if exc.stderr else "Unknown error"
            raise FFmpegError(stderr) from exc

    def _create_gif(
        self,
        source_path: Path,
        start: float,
        end: float,
        output_path: Path,
    ) -> None:
        input_stream = ffmpeg.input(str(source_path))

        video = input_stream.video.filter("trim", start=start, end=end).filter(
            "setpts", "PTS-STARTPTS"
        )

        palette_path = output_path.with_suffix(".png")

        try:
            palette_stream = video.filter("palettegen", max_colors=256)
            palette_out = ffmpeg.output(palette_stream, str(palette_path))
            palette_out = palette_out.overwrite_output()
            palette_out.run(capture_stdout=not self.verbose, capture_stderr=not self.verbose)
            palette_input = ffmpeg.input(str(palette_path))

            (
                ffmpeg.filter(
                    [video, palette_input.video],
                    "paletteuse",
                )
                .output(str(output_path))
                .overwrite_output()
                .run(capture_stdout=not self.verbose, capture_stderr=not self.verbose)
            )
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode("utf-8") if exc.stderr else "Unknown error"
            raise FFmpegError(stderr) from exc
        finally:
            if palette_path.exists():
                palette_path.unlink()

    def audio(
        self,
        source_path: Path,
        start: float,
        end: float,
        fmt: str | Format,
        output_dir: Path | None = None,
        overwrite: bool = False,
    ) -> AudioSpec:
        """Create an audio-only clip.

        Args:
            source_path: Path to source video/audio
            start: Start time in seconds
            end: End time in seconds
            fmt: Output format (m4a, wav, mp3)
            output_dir: Output directory (defaults to self.audio_dir)
            overwrite: Whether to overwrite existing files

        Returns:
            AudioSpec with audio clip metadata
        """
        if fmt not in self.SUPPORTED_AUDIO_FORMATS:
            raise UnsupportedFormatError(fmt)

        if output_dir is None:
            output_dir = self.audio_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = self._get_output_path(source_path, start, end, fmt, output_dir)

        if output_path.exists() and not overwrite:
            raise FileAlreadyExistsError(str(output_path))

        if not self._probe_audio(source_path):
            raise NoAudioStreamError(str(source_path))

        source_hash = compute_file_hash(str(source_path))
        created_at = datetime.now().isoformat()

        echo(f"Creating {fmt.upper()} audio: {output_path.name}", Color.INFO)

        self._create_audio_clip(source_path, start, end, fmt, output_path)

        spec = AudioSpec(
            artifact_path=str(output_path),
            start=start,
            end=end,
            format=fmt,
            ffmpeg_params=self._get_ffmpeg_params(fmt, audio=True),
            derived_from=str(source_path),
            source_hash=source_hash,
            created_at=created_at,
        )

        artifacts_file = output_dir / "artifacts.jsonl"
        ManifestManager.append_artifact_record(spec, artifacts_file)

        echo(f"Audio created: {output_path}", Color.SUCCESS)
        return spec

    def _create_audio_clip(
        self,
        source_path: Path,
        start: float,
        end: float,
        fmt: str | Format,
        output_path: Path,
    ) -> None:
        input_stream = ffmpeg.input(str(source_path))

        audio = input_stream.audio.filter(
            "atrim",
            start=start,
            end=end,
        ).filter("asetpts", "PTS-STARTPTS")

        output_kwargs = self._get_output_kwargs(fmt, audio=True)
        try:
            ffmpeg.output(
                audio,
                str(output_path),
                **output_kwargs,
            ).overwrite_output().run(
                capture_stdout=not self.verbose,
                capture_stderr=not self.verbose,
            )
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode("utf-8") if exc.stderr else "Unknown error"
            raise FFmpegError(stderr) from exc

    def _get_mac_output_kwargs(self, fmt: str | Format, audio: bool = False) -> dict:
        match fmt:
            case Format.MP4:
                return {"vcodec": "h264_videotoolbox", "acodec": "aac", "b:v": "10M"}
            case Format.MKV:
                return {"vcodec": "libx264", "acodec": "aac", "f": "matroska"}
            case Format.WEBM:
                return {"vcodec": "libvpx-vp9", "acodec": "libopus", "f": "webm"}
            case Format.GIF:
                return {}
            case Format.M4A:
                return {"acodec": "aac"}
            case Format.WAV:
                return {"acodec": "pcm_s16le"}
            case Format.MP3:
                return {"acodec": "libmp3lame"}
            case _:
                return {}

    # TODO: use audio param
    def _get_output_kwargs(self, fmt: str | Format, audio: bool = False) -> dict:
        if IS_MACOS:
            return self._get_mac_output_kwargs(fmt)

        match fmt:
            case Format.MP4:
                return {"vcodec": "libx264", "acodec": "aac", "movflags": "+faststart"}
            case Format.MKV:
                return {
                    "vcodec": "h264_videotoolbox",
                    "acodec": "aac",
                    "b:v": "10M",
                    "f": "matroska",
                }
            case Format.WEBM:
                return {"vcodec": "libvpx-vp9", "acodec": "libopus", "f": "webm"}
            case Format.GIF:
                return {}
            case Format.M4A:
                return {"acodec": "aac"}
            case Format.WAV:
                return {"acodec": "pcm_s16le"}
            case Format.MP3:
                return {"acodec": "libmp3lame"}
            case _:
                return {}

    def _get_ffmpeg_params(self, fmt: str | Format, audio: bool = False) -> dict:
        return self._get_output_kwargs(fmt, audio)
