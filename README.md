# maker

CLI tool to make stuff.

## Features

- **PDF Generation**: Convert image collections to PDF documents with customizable page sizes.
- **Resume to PDF**: Convert JSON/YAML resumes (jsonresume.org schema) to formatted PDFs.
- **YouTube Tools**: Download videos/playlists and process them into clips or audio.

## Installation

```sh
uv tool install .
```

## Usage

### PDF Generation

Convert images in a directory, glob pattern, or comma-separated list to a single PDF.

```sh
# Basic usage (images in directory)
maker pdf ./images -o output.pdf

# Using glob patterns
maker pdf "photos/*.jpg" -o gallery.pdf

# Explicit file list
maker pdf "img1.jpg,img2.png" -o bundle.pdf

# Specify paper size (A0-A10, B0-B10)
maker pdf ./docs -s A4 -v
```

#### Options

- `-o, --output`: Output PDF path (default: `output.pdf`)
- `-s, --size`: Page size A0-A10, B0-B10 (default: `A4`)
- `-v, --verbose`: Enable verbose logging

### Resume to PDF

Convert JSON or YAML resumes following the [JSON Resume](https://jsonresume.org) schema to formatted PDFs.

```sh
# Basic usage
maker resume resume.json -o output.pdf

# With custom font
maker resume resume.yaml --font "Roboto" --download-fonts

# Download Google Fonts automatically
maker resume resume.json --font Geist --download-fonts -v
```

#### Options

- `-o, --output`: Output PDF path (default: `resume.pdf`)
- `--font`: Font family name (default: `Helvetica`)
- `--download-fonts`: Download Google Fonts if not found locally
- `-v, --verbose`: Enable verbose logging

### Video Downloading

Manage YouTube downloads and processing.

#### Download Videos

```sh
# Download a video
maker yt download "https://youtube.com/watch?v=..."

# Download with custom alias and format
maker yt download "URL" --id my_video --format "bestvideo[height<=720]+bestaudio/best"

# Download entire playlist
maker yt download "PLAYLIST_URL" --playlist
```

#### Clipping and Processing

```sh
# Create a video clip from a previous download (using alias)
maker yt clip --src my_video --start 00:01:30 --end 00:02:00 --fmt mp4

# Create a high-quality GIF
maker yt clip --src local_video.mp4 --start 10.5 --end 15.2 --fmt gif

# Extract audio only
maker yt audio --src my_video --start 0 --end 60 --fmt mp3
```

#### Metadata and Management

```sh
# View video info (URL or alias)
maker yt info --src "URL"

# List all alias-managed downloads
maker yt list
```

#### Options

- `-v, --verbose`: Show detailed progress and FFmpeg output
- `--json`: Output results in JSON format for scripting

## Requirements

- **Python**: 3.11+
- **External**: [FFmpeg](https://ffmpeg.org/)
