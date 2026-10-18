# PDF Word Substituter

A small command-line tool that uses **PyMuPDF** to replace or remove text in PDF files. It keeps the original font and size when possible, places the new text on the same line as the old one, and **deletes** the old text from the file instead of just covering it, so it can't be found, selected or copied afterwards.

---

## 🌐 Repository
**GitHub Repository:** [pdf-word-substituter](https://github.com/Nahuelseoane/pdf-word-substituter)

---

## ✨ Features
- Replace a word or phrase in a PDF, or remove it completely.
- Old text is truly removed (not hidden under a white box), including leftover copies inside the file.
- Keeps the original font and size when possible (falls back to Helvetica, Times or Courier).
- Never changes the original file: saves a new `<name>_updated.pdf`.
- Tells you when the text isn't found instead of saving an unchanged copy.

---

## 🛠️ Requirements
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

---

## 📦 Installation

```bash
git clone https://github.com/Nahuelseoane/pdf-word-substituter.git
cd pdf-word-substituter
uv sync
```

---

## 🚀 Usage

```bash
# Replace text
uv run pdf-word-substituter fc.pdf "ABONO SERVICIO DE" "SERVICIO DE LIMPIEZA"

# Remove text (leave out the replacement)
uv run pdf-word-substituter "receipt.pdf" "Saldo de la cta cte: ARS -1.000,00"

# Choose where to save the result
uv run pdf-word-substituter fc.pdf "old text" "new text" -o /path/to/result.pdf
```

`uv run python script.py ...` works the same way.

- The search text must match exactly, including spaces and capital letters.
- The `.pdf` extension is optional.
- If the file isn't found as given, it is looked up in `DEFAULT_FOLDER` (set at the top of `src/pdf_word_substituter/substitute.py`).
- If the new text doesn't line up perfectly, adjust `x_offset` / `y_offset` in the same file.

---

## 📂 Project Structure

```
pdf-word-substituter/
├── src/pdf_word_substituter/
│   ├── __init__.py
│   └── substitute.py    # All the logic
├── script.py            # Shortcut for `uv run python script.py`
├── pyproject.toml       # Dependencies and the `pdf-word-substituter` command
└── uv.lock
```

---

## 🔧 Future Improvements

* Support for multiple replacements in one run.
* Embedding the original font instead of the closest standard one.
* GUI interface for easier use.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
