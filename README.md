# PDF Word Substituter

Replace or remove text in a PDF from the command line.

```bash
uv run pdf-word-substituter receipt.pdf "ABONO SERVICIO DE" "SERVICIO DE LIMPIEZA"
```

Unlike tools that paint a white box over the old text, this one **deletes it from the file**. Once it's removed, nobody can find it with a search, select it, copy it, or recover it from hidden data inside the PDF. That makes it safe for hiding sensitive details such as balances, account numbers or names before sharing a document.

---

## Features

- **Replace** a word or phrase with new text, or **remove** it completely.
- **Removes the old text for real**: removed text is deleted, along with any leftover copies inside the file.
- **Matches the original style**: keeps the font size and the closest standard font (Helvetica, Times or Courier), and places the new text on the same line as the old one.
- **Never touches the original**: the result is saved as a new file, `<name>_updated.pdf`.
- **Catches typos**: if the text isn't found, it tells you and saves nothing.
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
uv run pdf-word-substituter PDF TEXT [REPLACEMENT] [-o OUTPUT]
```

| Argument      | Description                                                                 |
| ------------- | --------------------------------------------------------------------------- |
| `PDF`         | The PDF to edit. The `.pdf` extension is optional.                          |
| `TEXT`        | The exact text to find, in quotes if it has spaces.                         |
| `REPLACEMENT` | The new text. **Leave it out to remove `TEXT`.**                            |
| `-o OUTPUT`   | Where to save the result. Default: `<name>_updated.pdf` next to the original. |

### Examples

Replace text:

```bash
uv run pdf-word-substituter invoice.pdf "ABONO SERVICIO DE" "SERVICIO DE LIMPIEZA"
```

Remove text:

```bash
uv run pdf-word-substituter "receipt.pdf" "Saldo de la cta cte: ARS -1.000,00"
```

Save somewhere else:

```bash
uv run pdf-word-substituter invoice.pdf "2025" "2026" -o ~/Documents/invoice_2026.pdf
```

`uv run python script.py ...` works exactly the same way.

### Tips

- The search is **exact**: spaces, accents and capital letters must match. If you're not sure, copy the text straight from the PDF viewer.
- If the file isn't found where you said, it's looked up in `DEFAULT_FOLDER`. Change that to your usual folder (e.g. Downloads) at the top of `src/pdf_word_substituter/substitute.py`.
- If the new text sits slightly off, nudge it with `x_offset` / `y_offset` in the same file.

---

## How it works

1. Finds every match of `TEXT` on each page.
2. Reads the font, size and position of each match while it still exists.
3. Deletes the matched text using PDF redaction. Images and lines are left untouched.
4. If there's a replacement, writes it at the same position with the closest standard font.
5. Saves with cleanup enabled, so the old page content isn't kept hidden inside the file.

## Limitations

- **Scanned PDFs** (text that is part of an image) aren't supported, because there's no real text to find.
- New text uses a standard font, so it may look slightly different if the PDF uses a custom font.
- New text is always black.
- A replacement much longer than the original can overlap whatever comes after it on the line.

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

- Several replacements in one run.
- Embedding the original font instead of the closest standard one.
- A simple graphical interface.

## License

MIT
