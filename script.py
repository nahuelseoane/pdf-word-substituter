"""Shortcut so `uv run python script.py ...` keeps working.

Same as running `uv run pdf-word-substituter ...`.
"""

from pdf_word_substituter import main

if __name__ == "__main__":
    main()
