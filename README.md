# PDF Word Substituter

Replace or remove text in a PDF from the command line.

```bash
uv run pdf-word-substituter receipt.pdf "ABONO SERVICIO DE" "SERVICIO DE LIMPIEZA"
```

Need several changes? Repeat `-r OLD NEW` (replace) and `-d TEXT` (remove), or list them in a [rules file](#rules-file):

```bash
uv run pdf-word-substituter receipt.pdf -r "Pilates" "Yoga" -d "Saldo de la cta cte: ARS -1.000,00"
```

Unlike tools that paint a white box over the old text, this one **deletes it from the file**. Once it's removed, nobody can find it with a search, select it, copy it, or recover it from hidden data inside the PDF. That makes it safe for hiding sensitive details such as balances, account numbers or names before sharing a document.

---

## Features

- **Replace** a word or phrase with new text, or **remove** it completely.
- **Several changes in one run**, from the command line or from a rules file.
- **Removes the old text for real**: removed text is deleted, along with any leftover copies inside the file.
- **Matches the original style**: keeps the font size and the closest standard font (Helvetica, Times or Courier), and places the new text on the same line as the old one.
- **Never touches the original**: the result is saved as a new file, `<name>_updated.pdf`.
- **Catches typos**: if some text isn't found, it tells you which, and if nothing was found it saves nothing.
- **Exact matching**: removing "Haedo" won't touch "HAEDO" unless you ask it to.
- Works on every page and every match in the document.

---

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/Nahuelseoane/pdf-word-substituter.git
cd pdf-word-substituter
uv sync
```

---

## Usage

```
uv run pdf-word-substituter PDF [TEXT [REPLACEMENT]] [-r OLD NEW] [-d TEXT] [-f FILE] [-i] [-o OUTPUT]
```

| Argument         | Description                                                                    |
| ---------------- | ------------------------------------------------------------------------------ |
| `PDF`            | The PDF to edit. The `.pdf` extension is optional.                             |
| `TEXT`           | The exact text to find, in quotes if it has spaces.                            |
| `REPLACEMENT`    | The new text. **Leave it out to remove `TEXT`.**                               |
| `-r OLD NEW`     | Replace `OLD` with `NEW`. Can be repeated.                                     |
| `-d TEXT`        | Remove `TEXT`. Can be repeated.                                                |
| `-f FILE`        | Read changes from a rules file (see below).                                    |
| `-i`             | Ignore capital letters when matching (`Haedo` also matches `HAEDO`).           |
| `-o OUTPUT`      | Where to save the result. Default: `<name>_updated.pdf` next to the original.  |

`TEXT`, `-r`, `-d` and `-f` can all be combined in one run.

### Examples

Replace text:

```bash
uv run pdf-word-substituter invoice.pdf "ABONO SERVICIO DE" "SERVICIO DE LIMPIEZA"
```

Remove text:

```bash
uv run pdf-word-substituter "receipt.pdf" "Saldo de la cta cte: ARS -1.000,00"
```

Several changes at once:

```bash
uv run pdf-word-substituter receipt.pdf -r "18/10/2026" "19/10/2026" -r "Pilates" "Yoga" -d "Saldo de la cta cte: ARS -1.000,00"
```

Save somewhere else:

```bash
uv run pdf-word-substituter invoice.pdf "2025" "2026" -o ~/Documents/invoice_2026.pdf
```

`uv run python script.py ...` works exactly the same way.

### Rules file

For changes you repeat often, put them in a text file, one per line:

```text
# receipt cleanup
Pilates => Yoga
18/10/2026 => 19/10/2026
Saldo de la cta cte: ARS -1.000,00
```

- `old => new` replaces; a line with just the text (or `old =>`) removes it.
- Blank lines and lines starting with `#` are ignored.
- Spaces at the start and end of each side are trimmed.

```bash
uv run pdf-word-substituter receipt.pdf -f rules.txt
```

### What you'll see

Each change is listed with how many times it was applied:

```text
  replaced   "Pilates" -> "Yoga" (1x)
  removed    "Saldo de la cta cte: ARS -1.000,00" (1x)
  NOT FOUND  "Typoo"
Updated PDF saved as receipt_updated.pdf
WARNING: 1 rule(s) not found; the rest were applied.
```

If some text isn't found, the rest is still applied and saved, but the command ends with a warning (and exit code 1) so a typo doesn't go unnoticed. If nothing is found, nothing is saved.

### Tips

- The search is **exact**: spaces, accents and capital letters must match (use `-i` to ignore capitals). If you're not sure, copy the text straight from the PDF viewer.
- If the file isn't found where you said, it's looked up in `DEFAULT_FOLDER`. Change that to your usual folder (e.g. Downloads) at the top of `src/pdf_word_substituter/substitute.py`.
- If the new text sits slightly off, nudge it with `x_offset` / `y_offset` in the same file.

---

## How it works

1. Finds every match of every change on each page. All changes are matched against the original text, so one change never affects text written by another.
2. Reads the font, size and position of each match while it still exists.
3. Deletes the matched text using PDF redaction. Images and lines are left untouched.
4. If there's a replacement, writes it at the same position with the closest standard font.
5. Saves with cleanup enabled, so the old page content isn't kept hidden inside the file.

## Limitations

- **Scanned PDFs** (text that is part of an image) aren't supported, because there's no real text to find.
- New text uses a standard font, so it may look slightly different if the PDF uses a custom font.
- New text is always black.
- A replacement much longer than the original can overlap whatever comes after it on the line.
- Text that wraps onto two lines can't be matched as one phrase; change each line separately.

---

## Project structure

```
pdf-word-substituter/
├── src/pdf_word_substituter/
│   ├── __init__.py
│   └── substitute.py    # All the logic and the command-line interface
├── script.py            # Shortcut for `uv run python script.py`
├── pyproject.toml       # Dependencies and the `pdf-word-substituter` command
└── uv.lock
```

## Ideas for later

- Embedding the original font instead of the closest standard one.
- A simple graphical interface.

## License

[MIT](LICENSE) © Nahuel Seoane
