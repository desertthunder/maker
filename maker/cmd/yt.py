"""YouTube video operations commands."""

import argparse
import json

from maker.shared import Color, echo, parse_range, format_time
from maker.video import Downloader, Cutter


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
    except Exception as e:
        echo(f"Download failed: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

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


def cmd_yt_clip(args: argparse.Namespace) -> int:
    """Handle video clip command."""
    try:
        start, end = parse_range(args.start, args.end)
        downloader = Downloader(downloads_dir=args.downloads_dir)
        source_path = downloader.resolve_source(args.src)

        cutter = Cutter(
            output_dir=args.out,
            ffmpeg_bin=args.ffmpeg_bin,
            verbose=args.verbose,
            overwrite=args.overwrite,
        )

        spec = cutter.clip(
            source_path=source_path,
            start=start,
            end=end,
            fmt=args.fmt,
            overwrite=args.overwrite,
            allow_no_audio=args.allow_no_audio,
        )
    except Exception as e:
        echo(f"Clip creation failed: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

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
            overwrite=args.overwrite,
        )

        spec = cutter.audio(
            source_path=source_path,
            start=start,
            end=end,
            fmt=args.fmt,
            overwrite=args.overwrite,
        )
    except Exception as e:
        echo(f"Audio creation failed: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

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


def _get_local_file_info(source_path, downloader) -> dict:
    """Extract video info from local file using ffprobe."""
    import ffmpeg

    probe = ffmpeg.probe(str(source_path))
    streams = probe.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(probe.get("format", {}).get("duration", 0))
    width = int(video_stream.get("width", 0)) if video_stream else 0
    height = int(video_stream.get("height", 0)) if video_stream else 0
    fps_str = video_stream.get("r_frame_rate", "0/1") if video_stream else "0/1"
    fps = int(fps_str.split("/")[0]) / int(fps_str.split("/")[1]) if "/" in fps_str else 0

    return {
        "title": source_path.stem,
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": audio_stream is not None,
        "path": str(source_path),
        "format": probe.get("format", {}).get("format_name", "unknown"),
    }


def _print_url_info(info, src) -> None:
    """Print info for URL source."""
    echo(f"Title: {info.get('title', 'Unknown')}", Color.INFO)
    echo(f"Duration: {format_time(info.get('duration', 0))}", Color.INFO)
    echo(f"Uploader: {info.get('uploader', 'Unknown')}", Color.INFO)
    echo(f"Views: {info.get('view_count', 0):,}", Color.INFO)
    echo(f"URL: {info.get('webpage_url', src)}", Color.INFO)


def _print_file_info(info) -> None:
    """Print info for local file source."""
    echo(f"File: {info.get('title', 'Unknown')}", Color.INFO)
    echo(f"Duration: {format_time(info.get('duration', 0))}", Color.INFO)
    echo(f"Resolution: {info.get('width', 0)}x{info.get('height', 0)}", Color.INFO)
    if info.get("fps"):
        echo(f"FPS: {info.get('fps', 0):.2f}", Color.INFO)
    echo(f"Has Audio: {'Yes' if info.get('has_audio') else 'No'}", Color.INFO)
    echo(f"Format: {info.get('format', 'unknown')}", Color.INFO)


def cmd_yt_info(args: argparse.Namespace) -> int:
    """Handle video info command."""
    downloader = Downloader(downloads_dir=args.downloads_dir, verbose=args.verbose)
    is_url = args.src.startswith(("http://", "https://"))

    try:
        if is_url:
            info = downloader.get_info(args.src)
        else:
            source_path = downloader.resolve_source(args.src)
            info = _get_local_file_info(source_path, downloader)
    except Exception as e:
        echo(f"Failed to get info: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    if args.json:
        print(json.dumps(info, indent=2))
    elif is_url:
        _print_url_info(info, args.src)
    else:
        _print_file_info(info)

    return 0


def cmd_yt_list(args: argparse.Namespace) -> int:
    """Handle list downloads command."""
    downloader = Downloader(downloads_dir=args.downloads_dir)

    try:
        downloads = downloader.list_downloads()
    except Exception as e:
        echo(f"Failed to list downloads: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

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
    elif not downloads:
        echo("No downloads found.", Color.INFO)
    else:
        echo("Downloaded videos:", Color.INFO)
        for alias, spec in downloads.items():
            echo(
                f"  {alias}: {spec.title} ({format_time(spec.duration)})",
                Color.INFO,
            )

    return 0
