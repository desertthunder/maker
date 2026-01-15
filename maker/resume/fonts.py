"""Font discovery and Google Fonts download functionality.

Searches system font directories for TTF files and optionally downloads
fonts from Google Fonts API for use with reportlab PDF generation.
"""

import json
import platform
import urllib.request
import urllib.error
from pathlib import Path
from dataclasses import dataclass

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

from maker.shared import FontNotFoundError, FontDownloadError


MAKER_FONTS_DIR = Path.home() / ".maker" / "fonts"
MANIFEST_FILE = MAKER_FONTS_DIR / "manifest.json"


@dataclass
class FontPaths:
    """Paths to font variants (regular, bold, italic, bold-italic)."""

    regular: Path
    bold: Path | None = None
    italic: Path | None = None
    bold_italic: Path | None = None


def get_system_font_dirs() -> list[Path]:
    """Return platform-specific system font directories."""
    system = platform.system()

    if system == "Darwin":
        return [
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
            Path("/System/Library/Fonts"),
        ]
    elif system == "Linux":
        return [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".local" / "share" / "fonts",
            Path.home() / ".fonts",
        ]
    elif system == "Windows":
        return [Path("C:/Windows/Fonts")]
    else:
        return []


def find_font_in_dirs(font_name: str, dirs: list[Path]) -> FontPaths | None:
    """Search directories for font files matching the given name.

    Looks for variations like FontName-Regular.ttf, FontName-Bold.ttf, etc.
    """
    name_lower = font_name.lower().replace(" ", "")
    variants = {
        "regular": ["-regular", "-roman", ""],
        "bold": ["-bold", "-semibold", "-medium"],
        "italic": ["-italic", "-oblique"],
        "bold_italic": ["-bolditalic", "-boldoblique"],
    }

    found: dict[str, Path | None] = {
        "regular": None,
        "bold": None,
        "italic": None,
        "bold_italic": None,
    }

    for font_dir in dirs:
        if not font_dir.exists():
            continue

        for ttf_file in font_dir.rglob("*.ttf"):
            file_lower = ttf_file.stem.lower().replace(" ", "")

            if not file_lower.startswith(name_lower):
                continue

            suffix = file_lower[len(name_lower) :]

            for variant, suffixes in variants.items():
                if any(suffix == s for s in suffixes):
                    if found[variant] is None:
                        found[variant] = ttf_file
                        break

    if found["regular"] is None:
        return None

    return FontPaths(
        regular=found["regular"],
        bold=found["bold"],
        italic=found["italic"],
        bold_italic=found["bold_italic"],
    )


def download_google_font(font_name: str) -> FontPaths:
    """Download font from Google Fonts API and cache locally.

    Fetches TTF files via the Google Fonts CSS2 API and stores
    them in ~/.maker/fonts/ with a manifest tracking downloads.
    """
    MAKER_FONTS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest()
    if font_name in manifest:
        paths = manifest[font_name]
        if Path(paths["regular"]).exists():
            return FontPaths(
                regular=Path(paths["regular"]),
                bold=Path(paths["bold"]) if paths.get("bold") else None,
                italic=Path(paths["italic"]) if paths.get("italic") else None,
                bold_italic=(Path(paths["bold_italic"]) if paths.get("bold_italic") else None),
            )

    font_dir = MAKER_FONTS_DIR / font_name.lower().replace(" ", "-")
    font_dir.mkdir(parents=True, exist_ok=True)

    downloaded: dict[str, Path | None] = {
        "regular": None,
        "bold": None,
        "italic": None,
        "bold_italic": None,
    }

    try:
        family_encoded = font_name.replace(" ", "+")
        css_url = f"https://fonts.googleapis.com/css2?family={family_encoded}:wght@400;700"
        req = urllib.request.Request(css_url, headers={"User-Agent": "Safari/5.0"})

        with urllib.request.urlopen(req, timeout=30) as response:
            css_content = response.read().decode("utf-8")

        font_faces = _extract_font_faces(css_content)
        if not font_faces:
            raise FontDownloadError(font_name, "No font URLs found in CSS response")

        for variant_key, font_url in font_faces:
            if downloaded[variant_key] is not None:
                continue

            ext = ".woff2" if "woff2" in font_url else ".ttf"
            file_name = f"{font_name.lower().replace(' ', '-')}-{variant_key}{ext}"
            file_path = font_dir / file_name

            _download_file(font_url, file_path)
            downloaded[variant_key] = file_path

    except urllib.error.URLError as e:
        raise FontDownloadError(font_name, str(e)) from e

    if downloaded["regular"] is None:
        raise FontDownloadError(font_name, "Failed to download regular variant")

    manifest[font_name] = {
        "regular": str(downloaded["regular"]),
        "bold": str(downloaded["bold"]) if downloaded["bold"] else None,
        "italic": str(downloaded["italic"]) if downloaded["italic"] else None,
        "bold_italic": (str(downloaded["bold_italic"]) if downloaded["bold_italic"] else None),
    }
    _save_manifest(manifest)

    return FontPaths(
        regular=downloaded["regular"],
        bold=downloaded["bold"],
        italic=downloaded["italic"],
        bold_italic=downloaded["bold_italic"],
    )


def _extract_font_faces(css_content: str) -> list[tuple[str, str]]:
    """Extract (variant, url) pairs from Google Fonts CSS response.

    Parses @font-face blocks to get font-weight, font-style, and src url.
    Returns list of (variant_key, url) tuples.
    """
    import re

    results = []
    blocks = re.findall(r"@font-face\s*\{([^}]+)\}", css_content)

    for block in blocks:
        url_match = re.search(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", block)
        weight_match = re.search(r"font-weight:\s*(\d+)", block)
        style_match = re.search(r"font-style:\s*(\w+)", block)

        if not url_match:
            continue

        url = url_match.group(1)
        weight = weight_match.group(1) if weight_match else "400"
        style = style_match.group(1) if style_match else "normal"

        is_bold = weight in ("700", "600", "800", "900")
        is_italic = style == "italic"

        if is_bold and is_italic:
            variant = "bold_italic"
        elif is_bold:
            variant = "bold"
        elif is_italic:
            variant = "italic"
        else:
            variant = "regular"

        results.append((variant, url))

    return results


def _download_file(url: str, dest: Path) -> None:
    """Download a file from URL to destination path."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        dest.write_bytes(response.read())


def _load_manifest() -> dict:
    """Load the font manifest file."""
    if not MANIFEST_FILE.exists():
        return {}
    with open(MANIFEST_FILE) as f:
        return json.load(f)


def _save_manifest(manifest: dict) -> None:
    """Save the font manifest file."""
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


def register_font(font_name: str, download: bool = False) -> str:
    """Register a font with reportlab for PDF generation.

    Searches system directories first, optionally downloading from Google Fonts.
    Returns the registered font family name for use in PDF generation.
    """
    system_dirs = get_system_font_dirs()
    system_dirs.append(MAKER_FONTS_DIR)

    for font_dir in system_dirs:
        if font_dir.exists():
            for subdir in font_dir.iterdir():
                if subdir.is_dir():
                    system_dirs.append(subdir)

    paths = find_font_in_dirs(font_name, system_dirs)

    if paths is None and download:
        paths = download_google_font(font_name)

    if paths is None:
        raise FontNotFoundError(font_name)

    base_name = font_name.replace(" ", "")

    pdfmetrics.registerFont(TTFont(base_name, str(paths.regular)))

    if paths.bold:
        pdfmetrics.registerFont(TTFont(f"{base_name}-Bold", str(paths.bold)))

    if paths.italic:
        pdfmetrics.registerFont(TTFont(f"{base_name}-Italic", str(paths.italic)))

    if paths.bold_italic:
        pdfmetrics.registerFont(TTFont(f"{base_name}-BoldItalic", str(paths.bold_italic)))

    registerFontFamily(
        base_name,
        normal=base_name,
        bold=f"{base_name}-Bold" if paths.bold else None,
        italic=f"{base_name}-Italic" if paths.italic else None,
        boldItalic=f"{base_name}-BoldItalic" if paths.bold_italic else None,
    )

    return base_name
