"""Replace (or remove) text in a PDF.

Usage:
    uv run pdf-word-substituter receipt.pdf "Saldo de la cta cte: ARS -1.000,00"
    uv run pdf-word-substituter fc.pdf "ABONO SERVICIO DE" "SERVICIO DE LIMPIEZA"

If the replacement is left out, the text is removed. If the PDF isn't found
as given, it is looked up in DEFAULT_FOLDER. The result is saved next to the
original as "<name>_updated.pdf" unless -o is given.
"""

import argparse
import sys
from pathlib import Path

import pymupdf

DEFAULT_FOLDER = Path("/mnt/c/Users/jnahu/Downloads")

# Fine-tune where the replacement text lands (0 = same spot as the old text)
x_offset = 0
y_offset = 0


def choose_fallback_font(original_font_name: str) -> str:
    name = original_font_name.lower()

    # Helvetica family
    if "helvetica" in name:
        if "bold" in name and ("oblique" in name or "italic" in name):
            return "hebi"
        elif "bold" in name:
            return "hebo"
        elif "oblique" in name or "italic" in name:
            return "heit"
        return "helv"

    # Times family
    if "times" in name:
        if "bold" in name and ("italic" in name or "oblique" in name):
            return "tibi"
        elif "bold" in name:
            return "tibo"
        elif "italic" in name or "oblique" in name:
            return "tiro"  # see note below
        return "tiro"

    # Courier family
    if "courier" in name:
        if "bold" in name and ("oblique" in name or "italic" in name):
            return "cobo"
        elif "bold" in name:
            return "cobo"
        elif "oblique" in name or "italic" in name:
            return "coit"
        return "cour"

    return "helv"


def find_span(page: pymupdf.Page, rect: pymupdf.Rect) -> dict | None:
    """Return the text span (font, size, baseline) that the found text is in."""
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span["text"].strip() and rect.intersects(span["bbox"]):
                    return span
    return None


def resolve_input(path_arg: str) -> Path:
    path = Path(path_arg)
    if path.suffix.lower() != ".pdf":
        path = path.with_name(path.name + ".pdf")
    if not path.exists() and not path.is_absolute():
        path = DEFAULT_FOLDER / path
    if not path.exists():
        sys.exit(f"PDF not found: {path_arg}")
    return path


def replace_text(pdf_path: Path, output_path: Path, old: str, new: str) -> int:
    """Replace `old` with `new` (or remove it if `new` is empty).

    Returns how many matches were changed. Nothing is saved if there are none.
    """
    doc = pymupdf.open(pdf_path)
    total = 0

    for page in doc:
        rects = page.search_for(old)
        if not rects:
            continue
        total += len(rects)

        # Read font and position before deleting, while the old text still exists
        spans = [find_span(page, rect) for rect in rects]

        # Delete the old text from the PDF itself (not just cover it), so it
        # can't be found, selected or copied. Images and lines are left alone.
        for rect in rects:
            page.add_redact_annot(rect, fill=False)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        )

        if not new:
            continue
        for rect, span in zip(rects, spans):
            detected_font = span["font"] if span else "helv"
            font_size = span["size"] if span else 8
            baseline = span["origin"][1] if span else rect.y1 - 2
            font_name = choose_fallback_font(detected_font)
            print(f"Detected PDF font: {detected_font} -> Using: {font_name}")
            page.insert_text(
                (rect.x0 + x_offset, baseline + y_offset),
                new,
                fontsize=font_size,
                fontname=font_name,
                color=(0, 0, 0),
            )

    if total:
        # garbage=4 drops unused objects (like the old, pre-redaction page
        # content), otherwise removed text can still be recovered from the file.
        doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace or remove text in a PDF.")
    parser.add_argument("pdf", help="PDF file (name or path)")
    parser.add_argument("text", help="exact text to find")
    parser.add_argument(
        "replacement", nargs="?", default="", help="new text (omit to remove)"
    )
    parser.add_argument("-o", "--output", help="output path")
    args = parser.parse_args()

    pdf_path = resolve_input(args.pdf)
    output_path = (
        Path(args.output)
        if args.output
        else pdf_path.with_name(f"{pdf_path.stem}_updated.pdf")
    )

    count = replace_text(pdf_path, output_path, args.text, args.replacement)
    if not count:
        sys.exit(
            f'Text not found in {pdf_path.name}: "{args.text}"\n'
            "Nothing was saved. Check spelling, spaces and capital letters."
        )
    action = "Replaced" if args.replacement else "Removed"
    print(f"{action} {count} match(es). Updated PDF saved as {output_path}")
