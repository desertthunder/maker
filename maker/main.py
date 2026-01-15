"""CLI entry point for maker tool."""

import argparse
import sys

from maker.shared import Format
from maker.video import Cutter
from maker.cmd import (
    cmd_pdf,
    cmd_yt_download,
    cmd_yt_clip,
    cmd_yt_audio,
    cmd_yt_info,
    cmd_yt_list,
    cmd_resume,
)


def main():
    parser = argparse.ArgumentParser(description="CLI tool to make stuff.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _setup_pdf_parser(subparsers)
    yt_parser = _setup_yt_parser(subparsers)
    _setup_resume_parser(subparsers)

    args = parser.parse_args()

    if args.command == "pdf":
        return cmd_pdf(args)
    elif args.command == "yt":
        return _dispatch_yt_command(args, yt_parser)
    elif args.command == "resume":
        return cmd_resume(args)
    else:
        parser.print_help()
        return 1


def _setup_pdf_parser(subparsers) -> None:
    """Configure PDF subparser."""
    pdf_parser = subparsers.add_parser("pdf", help="Convert images to PDF")
    pdf_parser.add_argument(
        "input",
        help="Directory path, glob pattern, or comma-separated list of image paths",
    )
    pdf_parser.add_argument(
        "-o", "--output", default="output.pdf", help="Output PDF path (default: output.pdf)"
    )
    pdf_parser.add_argument("-s", "--size", default="A4", help="Page size (default: A4)")
    pdf_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")


def _setup_yt_parser(subparsers):
    """Configure YouTube subparser and its subcommands."""
    yt_parser = subparsers.add_parser("yt", help="YouTube video operations")
    yt_subparsers = yt_parser.add_subparsers(dest="yt_command", help="YouTube commands")

    _setup_yt_download(yt_subparsers)
    _setup_yt_clip(yt_subparsers)
    _setup_yt_audio(yt_subparsers)
    _setup_yt_info(yt_subparsers)
    _setup_yt_list(yt_subparsers)

    return yt_parser


def _setup_yt_download(subparsers) -> None:
    """Configure download subcommand."""
    p = subparsers.add_parser("download", help="Download a YouTube video")
    p.add_argument("url", help="YouTube URL")
    p.add_argument("--id", help="Alias for the video (defaults to video ID)")
    p.add_argument("--out", default="downloads", help="Output directory (default: downloads/)")
    p.add_argument("--format", default="bestvideo+bestaudio/best", help="Video format")
    p.add_argument("--playlist", action="store_true", help="Download playlist")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    p.add_argument("--json", action="store_true", help="Output in JSON format")


def _setup_yt_clip(subparsers) -> None:
    """Configure clip subcommand."""
    p = subparsers.add_parser("clip", help="Create a video clip")
    p.add_argument("--src", required=True, help="Source alias or path")
    p.add_argument(
        "--start", required=True, help="Start time (HH:MM:SS.mmm, HH:MM:SS, or seconds)"
    )
    p.add_argument("--end", required=True, help="End time (HH:MM:SS.mmm, HH:MM:SS, or seconds)")
    p.add_argument("--out", default="clips", help="Output directory (default: clips/)")
    p.add_argument(
        "--fmt",
        default=Format.MP4.value,
        choices=[f.value for f in Format if f in Cutter.SUPPORTED_VIDEO_FORMATS],
        help="Output format",
    )
    p.add_argument(
        "--downloads-dir", default="downloads", help="Downloads directory for alias resolution"
    )
    p.add_argument("--ffmpeg-bin", help="Path to FFmpeg binary")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    p.add_argument("--allow-no-audio", action="store_true", help="Allow video-only output")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    p.add_argument("--json", action="store_true", help="Output in JSON format")


def _setup_yt_audio(subparsers) -> None:
    """Configure audio subcommand."""
    p = subparsers.add_parser("audio", help="Create an audio clip")
    p.add_argument("--src", required=True, help="Source alias or path")
    p.add_argument(
        "--start", required=True, help="Start time (HH:MM:SS.mmm, HH:MM:SS, or seconds)"
    )
    p.add_argument("--end", required=True, help="End time (HH:MM:SS.mmm, HH:MM:SS, or seconds)")
    p.add_argument("--out", default="audio", help="Output directory (default: audio/)")
    p.add_argument("--clips-out", default="clips", help="Clips output directory")
    p.add_argument(
        "--fmt",
        default=Format.M4A.value,
        choices=[f.value for f in Format if f in Cutter.SUPPORTED_AUDIO_FORMATS],
        help="Output format",
    )
    p.add_argument(
        "--downloads-dir", default="downloads", help="Downloads directory for alias resolution"
    )
    p.add_argument("--ffmpeg-bin", help="Path to FFmpeg binary")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    p.add_argument("--json", action="store_true", help="Output in JSON format")


def _setup_yt_info(subparsers) -> None:
    """Configure info subcommand."""
    p = subparsers.add_parser("info", help="Get video information")
    p.add_argument("--src", required=True, help="URL or alias")
    p.add_argument(
        "--downloads-dir", default="downloads", help="Downloads directory for alias resolution"
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    p.add_argument("--json", action="store_true", help="Output in JSON format")


def _setup_yt_list(subparsers) -> None:
    """Configure list subcommand."""
    p = subparsers.add_parser("list", help="List downloaded videos")
    p.add_argument("--downloads-dir", default="downloads", help="Downloads directory")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    p.add_argument("--json", action="store_true", help="Output in JSON format")


def _setup_resume_parser(subparsers) -> None:
    """Configure resume subparser."""
    p = subparsers.add_parser("resume", help="Convert resume to PDF")
    p.add_argument("input", help="Path to JSON or YAML resume file")
    p.add_argument(
        "-o", "--output", default="resume.pdf", help="Output PDF path (default: resume.pdf)"
    )
    p.add_argument("--font", default="Helvetica", help="Font family name (default: Helvetica)")
    p.add_argument(
        "--download-fonts", action="store_true", help="Download Google Fonts if not present"
    )
    p.add_argument("--theme", default="modern", help="Layout theme (default: modern)")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")


def _dispatch_yt_command(args, yt_parser) -> int:
    """Dispatch YouTube subcommand."""
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


if __name__ == "__main__":
    sys.exit(main())
