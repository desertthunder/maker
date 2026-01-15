from datetime import datetime
from pathlib import Path

import yt_dlp

from maker.shared import (
    DownloadSpec,
    ManifestManager,
    sanitize_filename,
    Color,
    echo,
)


class NotFoundForAliasError(FileNotFoundError):
    def __init__(self, source: str):
        super().__init__(f"Alias not found for source: {source}")


class Downloader:
    """YouTube video downloader using yt-dlp Python API."""

    DEFAULT_DOWNLOAD_DIR = Path("downloads")
    DEFAULT_FORMAT = "bestvideo+bestaudio/best"

    def __init__(
        self,
        downloads_dir: Path | str = DEFAULT_DOWNLOAD_DIR,
        verbose: bool = False,
    ):
        self.downloads_dir = Path(downloads_dir)
        self.verbose = verbose
        self._downloaded_files: list[dict] = []

    def _get_ydl_opts(
        self,
        alias: str,
        format: str = DEFAULT_FORMAT,
        playlist: bool = False,
    ) -> dict:
        """Build yt-dlp options dictionary."""
        return {
            "format": format,
            "noplaylist": not playlist,
            "outtmpl": {
                "default": f"{self.downloads_dir}/%({alias})s/%(title)s.%(ext)s",
            },
            "paths": {
                "home": str(self.downloads_dir),
            },
            "quiet": not self.verbose,
            "no_warnings": not self.verbose,
            "progress_hooks": [self._progress_hook] if self.verbose else [],
        }

    def _progress_hook(self, d: dict) -> None:
        """Progress hook for yt-dlp downloads."""
        if d["status"] == "downloading":
            if self.verbose:
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total > 0:
                    percent = downloaded / total * 100
                    echo(f"  Download progress: {percent:.1f}%", Color.INFO)
        elif d["status"] == "finished":
            echo("  Download complete, processing...", Color.INFO)
            filepath = d.get("filename") or d.get("filepath")
            if filepath:
                for existing in self._downloaded_files:
                    if existing.get("path") == filepath:
                        return
                self._downloaded_files.append(
                    {
                        "path": filepath,
                        "ext": Path(filepath).suffix.lstrip("."),
                        "filesize": d.get("total_bytes") or 0,
                    }
                )

    def download(
        self,
        url: str,
        alias: str | None = None,
        format: str = DEFAULT_FORMAT,
        playlist: bool = False,
    ) -> DownloadSpec:
        """Download a YouTube video.

        Args:
            url: YouTube URL
            alias: Optional alias for the video (defaults to video_id)
            format: yt-dlp format string
            playlist: Whether to download playlists

        Returns:
            DownloadSpec with download metadata
        """
        info = self.extract_info(url, download=False)

        video_id = info.get("id", "unknown")
        title = info.get("title", "Unknown Title")
        duration = info.get("duration", 0.0)

        if alias is None:
            alias = video_id

        sanitized_title = sanitize_filename(title)

        ydl_opts = {
            "format": format,
            "noplaylist": not playlist,
            "outtmpl": {
                "default": f"{alias}/{sanitized_title}.%(ext)s",
            },
            "paths": {
                "home": str(self.downloads_dir),
            },
            "quiet": not self.verbose,
            "no_warnings": not self.verbose,
            "progress_hooks": [self._progress_hook],
        }

        echo(f"Downloading: {title}", Color.INFO)

        self._downloaded_files = []
        start_time = datetime.now().isoformat()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        spec = DownloadSpec(
            source_url=url,
            video_id=video_id,
            alias=alias,
            downloaded_files=self._downloaded_files,
            yt_dlp_opts={"format": format, "noplaylist": not playlist},
            created_at=start_time,
            title=title,
            duration=duration,
        )

        ManifestManager.write_download_manifest(alias, spec, self.downloads_dir)

        echo(f"Downloaded to: {self.downloads_dir / alias}", Color.SUCCESS)
        return spec

    def extract_info(self, url: str, download: bool = False) -> dict:
        """Extract video info without downloading.

        Args:
            url: YouTube URL
            download: Whether to download (default: False)

        Returns:
            Dictionary with video metadata
        """
        ydl_opts = {
            "quiet": not self.verbose,
            "no_warnings": not self.verbose,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=download)

    def get_info(self, url: str) -> dict:
        """Get detailed information about a video.

        Args:
            url: YouTube URL or alias

        Returns:
            Dictionary with video metadata
        """
        try:
            info = self.extract_info(url, download=False)
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "view_count": info.get("view_count", 0),
                "upload_date": info.get("upload_date", "Unknown"),
                "description": info.get("description", "")[:500],
                "thumbnail": info.get("thumbnail", ""),
                "webpage_url": info.get("webpage_url", url),
            }
        except Exception as e:
            return {"error": str(e)}

    def list_downloads(self) -> dict[str, DownloadSpec]:
        """List all downloaded videos.

        Returns:
            Dictionary mapping alias to DownloadSpec
        """
        return ManifestManager.list_downloads(self.downloads_dir)

    def _validate_path(self, spec: DownloadSpec, source: str) -> Path:
        for file_info in spec.downloaded_files:
            path = Path(file_info["path"])
            if path.exists():
                return path
        raise NotFoundForAliasError(source)

    def resolve_source(self, source: str) -> Path:
        """Resolve a source (alias or path) to an actual file path.

        Args:
            source: Either an alias or a file path

        Returns:
            Path to the video file

        Raises:
            AliasNotFoundError: If alias is not found
        """
        try:
            spec = ManifestManager.read_download_manifest(source, self.downloads_dir)
            return self._validate_path(spec, source)
        except Exception:
            path = Path(source)
            if path.exists():
                return path
            raise
