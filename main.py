import argparse
import asyncio
import glob as glob_module
import os
from enum import Enum
from pathlib import Path
from typing import List, Tuple

from PIL import Image
from reportlab.pdfgen import canvas
from tqdm import tqdm


class Color(str, Enum):
    SUCCESS = "\033[92m"
    ERROR = "\033[91m"
    INFO = "\033[94m"
    WARNING = "\033[93m"
    RESET = "\033[0m"


def colored(text: str, color: Color) -> str:
    return f"{color.value}{text}{Color.RESET.value}"


class PaperSize(Enum):
    A0 = (2384, 3370)
    A1 = (1684, 2384)
    A2 = (1191, 1684)
    A3 = (842, 1191)
    A4 = (595, 842)
    A5 = (420, 595)
    A6 = (298, 420)
    A7 = (210, 298)
    A8 = (147, 210)
    A9 = (105, 147)
    A10 = (74, 105)
    B0 = (2835, 4008)
    B1 = (2004, 2835)
    B2 = (1417, 2004)
    B3 = (1001, 1417)
    B4 = (709, 1001)
    B5 = (499, 709)
    B6 = (354, 499)
    B7 = (249, 354)
    B8 = (176, 249)
    B9 = (125, 176)
    B10 = (88, 125)

    @property
    def width(self) -> int:
        return self.value[0]

    @property
    def height(self) -> int:
        return self.value[1]

    @staticmethod
    def from_string(size_str: str) -> "PaperSize":
        try:
            return PaperSize[size_str.upper()]
        except KeyError:
            raise ValueError(
                f"Invalid paper size: {size_str}. Valid sizes: {[s.name for s in PaperSize]}"
            )


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
    def get_image_dimensions(image_path: str) -> Tuple[int, int]:
        with Image.open(image_path) as img:
            return img.size

    @staticmethod
    def calculate_fit_size(
        img_width: int,
        img_height: int,
        page_width: int,
        page_height: int,
        margin: int = 36,
    ) -> Tuple[float, float, float, float]:
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
    def collect_images_from_directory(directory: str) -> List[str]:
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        images = []
        for file in dir_path.iterdir():
            if file.is_file() and ImageProcessor.is_supported_image(str(file)):
                images.append(str(file))
        return sorted(images)

    @staticmethod
    def collect_images_from_glob(pattern: str) -> List[str]:
        matches = glob_module.glob(pattern, recursive=True)
        images = [f for f in matches if ImageProcessor.is_supported_image(f)]
        return sorted(images)

    @staticmethod
    def collect_images_from_list(file_list: str) -> List[str]:
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
        self.output_path = output_path
        self.paper_size = paper_size
        self.verbose = verbose

    def create_pdf(self, image_paths: List[str]) -> None:
        total = len(image_paths)
        if total == 0:
            print(colored("No images to process!", Color.ERROR))
            return

        print(colored(f"Creating PDF with {total} image(s)...", Color.INFO))

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
                    print(colored(f"  Added: {Path(image_path).name}", Color.INFO))
            except Exception as e:
                print(colored(f"  Error processing {image_path}: {e}", Color.ERROR))

        c.save()
        print(colored(f"PDF created successfully: {self.output_path}", Color.SUCCESS))


async def process_input(input_arg: str) -> List[str]:
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
        else:
            raise ValueError(f"Invalid input: {input_arg}")

    return await loop.run_in_executor(None, collect)


def main():
    parser = argparse.ArgumentParser(description="Convert images to PDF")
    parser.add_argument(
        "input",
        help="Directory path, glob pattern, or comma-separated list of image paths",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output.pdf",
        help="Output PDF path (default: output.pdf)",
    )
    parser.add_argument("-s", "--size", default="A4", help="Page size (default: A4)")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        paper_size = PaperSize.from_string(args.size)
    except ValueError as e:
        print(colored(str(e), Color.ERROR))
        return 1

    image_paths = asyncio.run(process_input(args.input))

    if not image_paths:
        print(colored("No valid images found!", Color.ERROR))
        return 1

    generator = PDFGenerator(args.output, paper_size, args.verbose)
    generator.create_pdf(image_paths)

    return 0


if __name__ == "__main__":
    main()
