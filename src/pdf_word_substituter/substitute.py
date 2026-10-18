"""Replace (or remove) text in a PDF.

Usage:
    uv run pdf-word-substituter receipt.pdf "Saldo de la cta cte: ARS -1.000,00"
    uv run pdf-word-substituter fc.pdf "ABONO SERVICIO DE" "SERVICIO DE LIMPIEZA"
    uv run pdf-word-substituter fc.pdf -r "2025" "2026" -d "Saldo: ARS 100,00"
    uv run pdf-word-substituter fc.pdf -f rules.txt

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

    # Helvetica family (Arial has the same letter widths)
    if "helvetica" in name or "arial" in name:
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


def search_exact(
    page: pymupdf.Page, text: str, ignore_case: bool = False
) -> list[pymupdf.Rect]:
    """Find `text` on the page. PyMuPDF's search ignores capital letters, so
    unless `ignore_case` is set, keep only matches that are written exactly
    the same (removing "Haedo" must not also remove "HAEDO")."""
    rects = page.search_for(text)
    if ignore_case:
        return rects
    return [r for r in rects if page.get_textbox(r).strip() == text.strip()]


def resolve_input(path_arg: str) -> Path:
    path = Path(path_arg)
    if path.suffix.lower() != ".pdf":
        path = path.with_name(path.name + ".pdf")
    if not path.exists() and not path.is_absolute():
        path = DEFAULT_FOLDER / path
    if not path.exists():
        sys.exit(f"PDF not found: {path_arg}")
    return path


def replace_texts(
    pdf_path: Path,
    output_path: Path,
    rules: list[tuple[str, str]],
    ignore_case: bool = False,
) -> tuple[list[int], list[int]]:
    """Apply each (old, new) rule to the PDF; an empty `new` removes `old`.

    All rules are matched against the original text, so one rule never
    matches text inserted by another. Returns, per rule, how many matches
    were changed and how many were skipped because an earlier rule already
    changed that text. Nothing is saved if no rule matched.
    """
    if Path(output_path).resolve() == Path(pdf_path).resolve():
        raise ValueError("The output file must be different from the original PDF.")
    doc = pymupdf.open(pdf_path)
    counts = [0] * len(rules)
    skipped = [0] * len(rules)

    for page in doc:
        # (rect, span, new text) for every match of every rule on this page
        matches = []
        for i, (old, new) in enumerate(rules):
            for rect in search_exact(page, old, ignore_case):
                # Skip text already claimed by an earlier rule
                if any(rect.intersects(m[0]) for m in matches):
                    skipped[i] += 1
                    continue
                # Read font and position now, while the old text still exists
                matches.append((rect, find_span(page, rect), new))
                counts[i] += 1
        if not matches:
            continue

        # Delete the old text from the PDF itself (not just cover it), so it
        # can't be found, selected or copied. Images and lines are left alone.
        for rect, _, _ in matches:
            page.add_redact_annot(rect, fill=False)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        )

        for rect, span, new in matches:
            if not new:
                continue
            detected_font = span["font"] if span else "helv"
            font_size = span["size"] if span else 8
            baseline = span["origin"][1] if span else rect.y1 - 2
            page.insert_text(
                (rect.x0 + x_offset, baseline + y_offset),
                new,
                fontsize=font_size,
                fontname=choose_fallback_font(detected_font),
                color=(0, 0, 0),
            )

    if any(counts):
        # garbage=4 drops unused objects (like the old, pre-redaction page
        # content), otherwise removed text can still be recovered from the file.
        doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()
    return counts, skipped


def replace_text(
    pdf_path: Path, output_path: Path, old: str, new: str, ignore_case: bool = False
) -> int:
    """Single-rule version of replace_texts. Returns the number of matches."""
    counts, _ = replace_texts(pdf_path, output_path, [(old, new)], ignore_case)
    return counts[0]


def parse_rules(text: str) -> list[tuple[str, str]]:
    """Parse rules, one per line: "old => new", or "old" alone to remove it.

    Blank lines and lines starting with # are ignored. Spaces around each
    side are trimmed.
    """
    rules = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        old, _, new = line.partition("=>")
        if old.strip():
            rules.append((old.strip(), new.strip()))
    return rules


def read_rules_file(path_arg: str) -> list[tuple[str, str]]:
    path = Path(path_arg)
    if not path.exists():
        sys.exit(f"Rules file not found: {path_arg}")
    return parse_rules(path.read_text(encoding="utf-8"))


def summarize(
    rules: list[tuple[str, str]], counts: list[int], skipped: list[int]
) -> tuple[list[str], int]:
    """One report line per rule, plus how many rules weren't found."""
    lines = []
    missing = 0
    for (old, new), count, skip in zip(rules, counts, skipped):
        if not count and skip:
            lines.append(f'skipped    "{old}" (already changed by an earlier rule)')
        elif not count:
            missing += 1
            lines.append(f'NOT FOUND  "{old}"')
        elif new:
            lines.append(f'replaced   "{old}" -> "{new}" ({count}x)')
        else:
            lines.append(f'removed    "{old}" ({count}x)')
    return lines, missing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace or remove text in a PDF.",
        epilog="Rules from TEXT, -r, -d and -f can be combined in one run.",
    )
    parser.add_argument("pdf", help="PDF file (name or path)")
    parser.add_argument("text", nargs="?", help="exact text to find")
    parser.add_argument(
        "replacement", nargs="?", default="", help="new text (omit to remove)"
    )
    parser.add_argument(
        "-r",
        "--replace",
        nargs=2,
        action="append",
        default=[],
        metavar=("OLD", "NEW"),
        help="replace OLD with NEW (repeatable)",
    )
    parser.add_argument(
        "-d",
        "--remove",
        action="append",
        default=[],
        metavar="TEXT",
        help="remove TEXT (repeatable)",
    )
    parser.add_argument(
        "-f",
        "--rules-file",
        metavar="FILE",
        help='file with one rule per line: "old => new", or "old" to remove',
    )
    parser.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help='also match different capitals ("Haedo" matches "HAEDO")',
    )
    parser.add_argument("-o", "--output", help="output path")
    args = parser.parse_args()

    rules: list[tuple[str, str]] = []
    if args.text:
        rules.append((args.text, args.replacement))
    rules += [(old, new) for old, new in args.replace]
    rules += [(text, "") for text in args.remove]
    if args.rules_file:
        rules += read_rules_file(args.rules_file)
    if not rules:
        parser.error("nothing to do: give TEXT, -r, -d or -f")

    pdf_path = resolve_input(args.pdf)
    output_path = (
        Path(args.output)
        if args.output
        else pdf_path.with_name(f"{pdf_path.stem}_updated.pdf")
    )

    try:
        counts, skipped = replace_texts(pdf_path, output_path, rules, args.ignore_case)
    except ValueError as e:
        sys.exit(str(e))

    lines, missing = summarize(rules, counts, skipped)
    for line in lines:
        print(f"  {line}")

    if not any(counts):
        sys.exit(
            f"No text found in {pdf_path.name}. Nothing was saved.\n"
            "Check spelling, spaces and capital letters."
        )
    print(f"Updated PDF saved as {output_path}")
    if missing:
        # Exit with an error so a missed rule (e.g. a typo) isn't overlooked
        sys.exit(f"WARNING: {missing} rule(s) not found; the rest were applied.")
