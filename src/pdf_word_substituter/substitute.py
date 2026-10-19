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
import re
import sys
from dataclasses import dataclass
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
    """Return the text span (font, size, baseline) that the found text is in,
    picking the one that overlaps it the most."""
    best, best_area = None, 0.0
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if not span["text"].strip():
                    continue
                area = (rect & pymupdf.Rect(span["bbox"])).get_area()
                if area > best_area:
                    best, best_area = span, area
    return best


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


Word = tuple[str, pymupdf.Rect]


def visual_lines(page: pymupdf.Page) -> list[list[Word]]:
    """Group the page's words into lines as they look on screen, left to right.

    Words that sit side by side end up on the same line even when the PDF
    stores them as separate pieces (like "CUIT:" and its value in another
    column), which a plain search can't match as one phrase.
    """
    words = sorted(
        ((w[4], pymupdf.Rect(w[:4])) for w in page.get_text("words")),
        key=lambda w: (w[1].y0 + w[1].y1) / 2,
    )
    lines: list[list[Word]] = []
    line_center = 0.0
    for text, rect in words:
        center = (rect.y0 + rect.y1) / 2
        if lines and abs(center - line_center) <= rect.height * 0.3:
            lines[-1].append((text, rect))
        else:
            lines.append([(text, rect)])
            line_center = center
    for line in lines:
        line.sort(key=lambda w: w[1].x0)
    return lines


def find_word_sequences(
    lines: list[list[Word]], tokens: list[str], ignore_case: bool
) -> list[list[pymupdf.Rect]]:
    """Find whole words `tokens` next to each other on one line. Returns one
    rect per word for each match."""
    norm = str.casefold if ignore_case else str
    want = [norm(t) for t in tokens]
    found = []
    for line in lines:
        texts = [norm(t) for t, _ in line]
        i = 0
        while i + len(want) <= len(texts):
            if texts[i : i + len(want)] == want:
                found.append([r for _, r in line[i : i + len(want)]])
                i += len(want)
            else:
                i += 1
    return found


def find_matches(
    page: pymupdf.Page, old: str, ignore_case: bool, lines: list[list[Word]]
) -> list[tuple[list[pymupdf.Rect], bool]]:
    """All matches of `old` on the page, as (rects, one_rect_per_word).

    Whole words are matched along visual lines first; the plain search then
    adds matches inside words (like "-35.344" in "-35.344.754,00").
    """
    tokens = old.split()
    if not tokens:
        return []
    matches = [(r, True) for r in find_word_sequences(lines, tokens, ignore_case)]
    for rect in search_exact(page, old, ignore_case):
        if not any(rect.intersects(r) for rects, _ in matches for r in rects):
            matches.append(([rect], False))
    return matches


@dataclass
class Change:
    claim: list[pymupdf.Rect]  # all of the matched text
    delete: list[pymupdf.Rect]  # the part that actually changes
    text: str  # what to write ("" = nothing)
    x: float
    baseline: float
    font: str
    size: float


def plan_change(
    page: pymupdf.Page, rects: list[pymupdf.Rect], per_word: bool, old: str, new: str
) -> Change:
    """Work out what to delete and what to write for one match.

    Words that old and new share at the start or end are left as they are,
    so "CUIT: -" => "CUIT: 20-12345678-9" only swaps the "-" for the number,
    in the spot where the "-" was.
    """
    keep_start = keep_end = 0
    delete, text = rects, new
    if per_word and new:
        old_words, new_words = old.split(), new.split()
        shortest = min(len(old_words), len(new_words))
        while keep_start < shortest and old_words[keep_start] == new_words[keep_start]:
            keep_start += 1
        while (
            keep_end < shortest - keep_start
            and old_words[-1 - keep_end] == new_words[-1 - keep_end]
        ):
            keep_end += 1
        delete = rects[keep_start : len(rects) - keep_end]
        # The changed words of `new`, with the spacing the user typed
        spans = [m.span() for m in re.finditer(r"\S+", new)]
        last = len(spans) - keep_end - 1
        text = new[spans[keep_start][0] : spans[last][1]] if keep_start <= last else ""

    anchor = delete[0] if delete else rects[max(keep_start - 1, 0)]
    span = find_span(page, anchor)
    font = choose_fallback_font(span["font"]) if span else "helv"
    size = span["size"] if span else 8
    baseline = span["origin"][1] if span else anchor.y1 - 2

    space = pymupdf.get_text_length(" ", font, size)
    if delete:  # write where the old text was
        x = delete[0].x0
    elif keep_start:  # only adding: write after the kept words
        x = rects[keep_start - 1].x1 + space
    else:  # only adding, before the kept words
        x = rects[0].x0 - space - pymupdf.get_text_length(text, font, size)
    return Change(rects, delete, text, x, baseline, font, size)


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
        lines = visual_lines(page)
        changes: list[Change] = []
        for i, (old, new) in enumerate(rules):
            for rects, per_word in find_matches(page, old, ignore_case, lines):
                # Skip text already claimed by an earlier rule
                claimed = [c for ch in changes for c in ch.claim]
                if any(r.intersects(c) for r in rects for c in claimed):
                    skipped[i] += 1
                    continue
                # Plan now, while the old text (and its font) still exists
                changes.append(plan_change(page, rects, per_word, old, new))
                counts[i] += 1

        # Delete the old text from the PDF itself (not just cover it), so it
        # can't be found, selected or copied. Images and lines are left alone.
        to_delete = [r for ch in changes for r in ch.delete]
        for rect in to_delete:
            page.add_redact_annot(rect, fill=False)
        if to_delete:
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            )

        for ch in changes:
            if ch.text:
                page.insert_text(
                    (ch.x + x_offset, ch.baseline + y_offset),
                    ch.text,
                    fontsize=ch.size,
                    fontname=ch.font,
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
