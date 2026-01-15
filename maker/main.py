import argparse
import asyncio
import glob as glob_module
import json
import os
import sys
from pathlib import Path

from PIL import Image
from reportlab.pdfgen import canvas
from tqdm import tqdm

from maker.shared import (
    Color,
    echo,
    PaperSize,
    InvalidInputError,
    NotADirectoryError,
    parse_range,
    format_time,
)
from maker.video import Downloader, Cutter


class ImageProcessor:
    SUPPORTED_FORMATS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".gif",
        ".tiff",
        ".tif",
    }

    @staticmethod
    def get_image_dimensions(image_path: str) -> tuple[int, int]:
        with Image.open(image_path) as img:
            return img.size

    @staticmethod
    def calculate_fit_size(
        img_width: int,
        img_height: int,
        page_width: int,
        page_height: int,
        margin: int = 36,
    ) -> tuple[float, float, float, float]:
        usable_width = page_width - 2 * margin
        usable_height = page_height - 2 * margin

        width_ratio = usable_width / img_width
        height_ratio = usable_height / img_height
        scale_factor = min(width_ratio, height_ratio)

        scaled_width = img_width * scale_factor
        scaled_height = img_height * scale_factor

        x = (page_width - scaled_width) / 2
        y = (page_height - scaled_height) / 2

        return x, y, scaled_width, scaled_height

    @staticmethod
    def is_supported_image(path: str) -> bool:
        return Path(path).suffix.lower() in ImageProcessor.SUPPORTED_FORMATS

    @staticmethod
    def collect_images_from_directory(directory: str) -> list[str]:
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise NotADirectoryError(directory)

        return sorted(
            [
                str(f)
                for f in dir_path.iterdir()
                if f.is_file() and ImageProcessor.is_supported_image(str(f))
            ]
        )

    @staticmethod
    def collect_images_from_glob(pattern: str) -> list[str]:
        matches = glob_module.glob(pattern, recursive=True)
        images = [f for f in matches if ImageProcessor.is_supported_image(f)]
        return sorted(images)

    @staticmethod
    def collect_images_from_list(file_list: str) -> list[str]:
        files = [f.strip() for f in file_list.split(",")]
        images = [
            f
            for f in files
            if Path(f).is_file() and ImageProcessor.is_supported_image(f)
        ]
        return sorted(images)


class PDFGenerator:
    def __init__(
        self,
        output_path: str,
        paper_size: PaperSize = PaperSize.A4,
        verbose: bool = False,
    ):
        self.output_path: str = output_path
        self.paper_size: PaperSize = paper_size
        self.verbose: bool = verbose

    def create_pdf(self, image_paths: list[str]) -> None:
        total = len(image_paths)
        if total == 0:
            echo("No images to process!", Color.ERROR)
            return

        echo(f"Creating PDF with {total} image(s)...", Color.INFO)

        c = canvas.Canvas(
            self.output_path, pagesize=(self.paper_size.width, self.paper_size.height)
        )
        page_width, page_height = self.paper_size.width, self.paper_size.height

        for image_path in tqdm(image_paths, desc="Processing images"):
            try:
                img_width, img_height = ImageProcessor.get_image_dimensions(image_path)
                x, y, scaled_width, scaled_height = ImageProcessor.calculate_fit_size(
                    img_width, img_height, page_width, page_height
                )

                c.drawImage(image_path, x, y, scaled_width, scaled_height, mask="auto")
                c.showPage()

                if self.verbose:
                    echo(f"  Added: {Path(image_path).name}", Color.INFO)
            except Exception as e:  # noqa: PERF203
                echo(f"  Error processing {image_path}: {e}", Color.ERROR)

        c.save()
        echo(f"PDF created successfully: {self.output_path}", Color.SUCCESS)


async def process_input(input_arg: str) -> list[str]:
    loop = asyncio.get_event_loop()

    def collect():
        if os.path.isdir(input_arg):
            return ImageProcessor.collect_images_from_directory(input_arg)
        elif "*" in input_arg or "?" in input_arg:
            return ImageProcessor.collect_images_from_glob(input_arg)
        elif "," in input_arg:
            return ImageProcessor.collect_images_from_list(input_arg)
        elif os.path.isfile(input_arg):
            return [input_arg] if ImageProcessor.is_supported_image(input_arg) else []

        raise InvalidInputError(input_arg)

    return await loop.run_in_executor(None, collect)


def cmd_pdf(args: argparse.Namespace) -> int:
    """Handle PDF generation (default command)."""
    try:
        paper_size = PaperSize.from_string(args.size)
    except ValueError as e:
        echo(str(e), Color.ERROR)
        return 1

    image_paths = asyncio.run(process_input(args.input))

    if not image_paths:
        echo("No valid images found!", Color.ERROR)
        return 1

    generator = PDFGenerator(args.output, paper_size, args.verbose)
    generator.create_pdf(image_paths)

    return 0


def cmd_yt_download(args: argparse.Namespace) -> int:
    """Handle YouTube download command."""
    downloader = Downloader(
        downloads_dir=args.out,
        verbose=args.verbose,
    )

    try:
        spec = downloader.download(
            url=args.url,
            alias=args.id,
            format=args.format,
            playlist=args.playlist,
        )

        if args.json:
            output = json.dumps(
                {
                    "alias": spec.alias,
                    "video_id": spec.video_id,
                    "title": spec.title,
                    "duration": spec.duration,
                    "files": spec.downloaded_files,
                    "created_at": spec.created_at,
                },
                indent=2,
            )
            print(output)
            return 0
        else:
            return 0
    except Exception as e:
        echo(f"Download failed: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def cmd_yt_clip(args: argparse.Namespace) -> int:
    """Handle video clip command."""
    try:
        start, end = parse_range(args.start, args.end)
        downloader = Downloader(downloads_dir=args.downloads_dir)
        source_path = downloader.resolve_source(args.src)

        cutter = Cutter(
            output_dir=args.out,
            audio_dir=args.audio_out,
            ffmpeg_bin=args.ffmpeg_bin,
            verbose=args.verbose,
        )

        spec = cutter.clip(
            source_path=source_path,
            start=start,
            end=end,
            fmt=args.fmt,
            overwrite=args.overwrite,
            allow_no_audio=args.allow_no_audio,
        )

        if args.json:
            output = json.dumps(
                {
                    "artifact": spec.artifact_path,
                    "start": spec.start,
                    "end": spec.end,
                    "format": spec.format,
                    "derived_from": spec.derived_from,
                    "created_at": spec.created_at,
                },
                indent=2,
            )
            print(output)
            return 0
        else:
            return 0
    except Exception as e:
        echo(f"Clip creation failed: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def cmd_yt_audio(args: argparse.Namespace) -> int:
    """Handle audio clip command."""
    try:
        start, end = parse_range(args.start, args.end)
        downloader = Downloader(downloads_dir=args.downloads_dir)
        source_path = downloader.resolve_source(args.src)

        cutter = Cutter(
            output_dir=args.clips_out,
            audio_dir=args.out,
            ffmpeg_bin=args.ffmpeg_bin,
            verbose=args.verbose,
        )

        spec = cutter.audio(
            source_path=source_path,
            start=start,
            end=end,
            fmt=args.fmt,
            overwrite=args.overwrite,
        )

        if args.json:
            output = json.dumps(
                {
                    "artifact": spec.artifact_path,
                    "start": spec.start,
                    "end": spec.end,
                    "format": spec.format,
                    "derived_from": spec.derived_from,
                    "created_at": spec.created_at,
                },
                indent=2,
            )
            print(output)
            return 0
        else:
            return 0
    except Exception as e:
        echo(f"Audio creation failed: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def cmd_yt_info(args: argparse.Namespace) -> int:
    """Handle video info command."""
    downloader = Downloader(downloads_dir=args.downloads_dir, verbose=args.verbose)

    try:
        if args.src.startswith(("http://", "https://")):
            info = downloader.get_info(args.src)
        else:
            source_path = downloader.resolve_source(args.src)
            import ffmpeg

            probe = ffmpeg.probe(str(source_path))
            streams = probe.get("streams", [])

            video_stream = next(
                (s for s in streams if s.get("codec_type") == "video"), None
            )
            audio_stream = next(
                (s for s in streams if s.get("codec_type") == "audio"), None
            )

            duration = float(probe.get("format", {}).get("duration", 0))
            width = int(video_stream.get("width", 0)) if video_stream else 0
            height = int(video_stream.get("height", 0)) if video_stream else 0
            fps_str = video_stream.get("r_frame_rate", "0/1") if video_stream else "0/1"
            fps = (
                int(fps_str.split("/")[0]) / int(fps_str.split("/")[1])
                if "/" in fps_str
                else 0
            )

            info = {
                "title": source_path.stem,
                "duration": duration,
                "width": width,
                "height": height,
                "fps": fps,
                "has_audio": audio_stream is not None,
                "path": str(source_path),
                "format": probe.get("format", {}).get("format_name", "unknown"),
            }

        if args.json:
            print(json.dumps(info, indent=2))
            return 0
        else:
            if args.src.startswith(("http://", "https://")):
                echo(f"Title: {info.get('title', 'Unknown')}", Color.INFO)
                echo(f"Duration: {format_time(info.get('duration', 0))}", Color.INFO)
                echo(f"Uploader: {info.get('uploader', 'Unknown')}", Color.INFO)
                echo(f"Views: {info.get('view_count', 0):,}", Color.INFO)
                echo(f"URL: {info.get('webpage_url', args.src)}", Color.INFO)
            else:
                echo(f"File: {info.get('title', 'Unknown')}", Color.INFO)
                echo(f"Duration: {format_time(info.get('duration', 0))}", Color.INFO)
                echo(
                    f"Resolution: {info.get('width', 0)}x{info.get('height', 0)}",
                    Color.INFO,
                )
                if info.get("fps"):
                    echo(f"FPS: {info.get('fps', 0):.2f}", Color.INFO)
                echo(
                    f"Has Audio: {'Yes' if info.get('has_audio') else 'No'}", Color.INFO
                )
                echo(f"Format: {info.get('format', 'unknown')}", Color.INFO)

            return 0
    except Exception as e:
        echo(f"Failed to get info: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def cmd_yt_list(args: argparse.Namespace) -> int:
    """Handle list downloads command."""
    downloader = Downloader(downloads_dir=args.downloads_dir)

    try:
        downloads = downloader.list_downloads()

        if args.json:
            output = {}
            for alias, spec in downloads.items():
                output[alias] = {
                    "title": spec.title,
                    "duration": spec.duration,
                    "created_at": spec.created_at,
                    "files": spec.downloaded_files,
                }
            print(json.dumps(output, indent=2))
            return 0
        else:
            if not downloads:
                echo("No downloads found.", Color.INFO)
            else:
                echo("Downloaded videos:", Color.INFO)
                for alias, spec in downloads.items():
                    echo(
                        f"  {alias}: {spec.title} ({format_time(spec.duration)})",
                        Color.INFO,
                    )

            return 0
    except Exception as e:
        echo(f"Failed to list downloads: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(description="CLI tool to make stuff.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    pdf_parser = subparsers.add_parser("pdf", help="Convert images to PDF")
    pdf_parser.add_argument(
        "input",
        help="Directory path, glob pattern, or comma-separated list of image paths",
    )
    pdf_parser.add_argument(
        "-o",
        "--output",
        default="output.pdf",
        help="Output PDF path (default: output.pdf)",
    )
    pdf_parser.add_argument(
        "-s", "--size", default="A4", help="Page size (default: A4)"
    )
    pdf_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    yt_parser = subparsers.add_parser("yt", help="YouTube video operations")
    yt_subparsers = yt_parser.add_subparsers(dest="yt_command", help="YouTube commands")

    yt_download = yt_subparsers.add_parser("download", help="Download a YouTube video")
    yt_download.add_argument("url", help="YouTube URL")
    yt_download.add_argument("--id", help="Alias for the video (defaults to video ID)")
    yt_download.add_argument(
        "--out", default="downloads", help="Output directory (default: downloads/"
    )
    yt_download.add_argument(
        "--format", default="bestvideo+bestaudio/best", help="Video format"
    )
    yt_download.add_argument(
        "--playlist", action="store_true", help="Download playlist"
    )
    yt_download.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    yt_download.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )

    yt_clip = yt_subparsers.add_parser("clip", help="Create a video clip")
    yt_clip.add_argument("--src", required=True, help="Source alias or path")
    yt_clip.add_argument(
        "--start", required=True, help="Start time (HH:MM:SS.mmm, HH:MM:SS, or seconds)"
    )
    yt_clip.add_argument(
        "--end", required=True, help="End time (HH:MM:SS.mmm, HH:MM:SS, or seconds)"
    )
    yt_clip.add_argument(
        "--out", default="clips", help="Output directory (default: clips/)"
    )
    yt_clip.add_argument(
        "--fmt",
        default="mp4",
        choices=["mp4", "mkv", "webm", "gif"],
        help="Output format",
    )
    yt_clip.add_argument(
        "--downloads-dir",
        default="downloads",
        help="Downloads directory for alias resolution",
    )
    yt_clip.add_argument("--ffmpeg-bin", help="Path to FFmpeg binary")
    yt_clip.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files"
    )
    yt_clip.add_argument(
        "--allow-no-audio", action="store_true", help="Allow video-only output"
    )
    yt_clip.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    yt_clip.add_argument("--json", action="store_true", help="Output in JSON format")

    yt_audio = yt_subparsers.add_parser("audio", help="Create an audio clip")
    yt_audio.add_argument("--src", required=True, help="Source alias or path")
    yt_audio.add_argument(
        "--start", required=True, help="Start time (HH:MM:SS.mmm, HH:MM:SS, or seconds)"
    )
    yt_audio.add_argument(
        "--end", required=True, help="End time (HH:MM:SS.mmm, HH:MM:SS, or seconds)"
    )
    yt_audio.add_argument(
        "--out", default="audio", help="Output directory (default: audio/)"
    )
    yt_audio.add_argument("--clips-out", default="clips", help="Clips output directory")
    yt_audio.add_argument(
        "--fmt", default="m4a", choices=["m4a", "wav", "mp3"], help="Output format"
    )
    yt_audio.add_argument(
        "--downloads-dir",
        default="downloads",
        help="Downloads directory for alias resolution",
    )
    yt_audio.add_argument("--ffmpeg-bin", help="Path to FFmpeg binary")
    yt_audio.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files"
    )
    yt_audio.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    yt_audio.add_argument("--json", action="store_true", help="Output in JSON format")

    yt_info = yt_subparsers.add_parser("info", help="Get video information")
    yt_info.add_argument("--src", required=True, help="URL or alias")
    yt_info.add_argument(
        "--downloads-dir",
        default="downloads",
        help="Downloads directory for alias resolution",
    )
    yt_info.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    yt_info.add_argument("--json", action="store_true", help="Output in JSON format")

    yt_list = yt_subparsers.add_parser("list", help="List downloaded videos")
    yt_list.add_argument(
        "--downloads-dir", default="downloads", help="Downloads directory"
    )
    yt_list.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    yt_list.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    if args.command == "pdf":
        return cmd_pdf(args)
    elif args.command == "yt":
        if args.yt_command == "download":
            return cmd_yt_download(args)
        elif args.yt_command == "clip":
            return cmd_yt_clip(args)
        elif args.yt_command == "audio":
            return cmd_yt_audio(args)
        elif args.yt_command == "info":
            return cmd_yt_info(args)
        elif args.yt_command == "list":
            return cmd_yt_list(args)
        else:
            yt_parser.print_help()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
