# makepdf

CLI tool to convert images to PDF.

## Installation

```bash
uv tool install .
```

## Usage

```bash
makepdf [input] [options]
```

### Directory (all images)

```bash
makepdf ./images -o output.pdf
```

### Glob pattern

```bash
makepdf "*.jpg" -o output.pdf
```

### Comma-separated list

```bash
makepdf "img1.jpg,img2.png,img3.webp" -o output.pdf
```

### Options

- `-o, --output`: Output PDF path (default: `output.pdf`)
- `-s, --size`: Page size A0-A10, B0-B10 (default: `A4`)
- `-v, --verbose`: Show detailed progress

## Example

```bash
makepdf ./photos -s A3 -v
```
