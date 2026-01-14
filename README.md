# makepdf

CLI/script to convert a collection of images to PDF.

## Installation

```sh
uv tool install .
```

## Usage

```sh
makepdf [input] [options]

# Directory (all images)
makepdf ./images -o output.pdf

# Glob pattern
makepdf "*.jpg" -o output.pdf

# Comma-separated list
makepdf "img1.jpg,img2.png,img3.webp" -o output.pdf
```

### Options

- `-o, --output`: Output PDF path (default: `output.pdf`)
- `-s, --size`: Page size A0-A10, B0-B10 (default: `A4`)
- `-v, --verbose`: Show detailed progress

### Example

```sh
makepdf ./photos -s A3 -v
```
