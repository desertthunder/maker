"""Resume to PDF conversion command."""

import argparse
import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from maker.shared import Color, echo
from maker.resume import Resume, ResumeGenerator


def _load_resume_data(input_path: Path) -> dict | None:
    suffix = input_path.suffix.lower()

    try:
        with open(input_path) as f:
            if suffix == ".json":
                return json.load(f)
            return yaml.safe_load(f)
    except json.JSONDecodeError as e:
        echo(f"Invalid JSON: {e}", Color.ERROR)
    except yaml.YAMLError as e:
        echo(f"Invalid YAML: {e}", Color.ERROR)
    return None


def cmd_resume(args: argparse.Namespace) -> int:
    """Handle resume to PDF conversion."""
    input_path = Path(args.input)

    if not input_path.exists():
        echo(f"Input file not found: {input_path}", Color.ERROR)
        return 1

    if input_path.suffix.lower() not in (".json", ".yaml", ".yml"):
        echo("Unsupported file format. Use .json or .yaml", Color.ERROR)
        return 1

    data = _load_resume_data(input_path)
    if data is None:
        return 1

    try:
        resume = Resume.model_validate(data)
    except ValidationError as e:
        echo("Resume validation failed:", Color.ERROR)
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            echo(f"  {loc}: {error['msg']}", Color.ERROR)
        return 1

    try:
        generator = ResumeGenerator(
            font_name=args.font,
            download_fonts=args.download_fonts,
            verbose=args.verbose,
        )
        generator.generate(resume, Path(args.output))
    except Exception as e:
        echo(f"PDF generation failed: {e}", Color.ERROR)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    echo(f"Resume PDF created: {args.output}", Color.SUCCESS)
    return 0
