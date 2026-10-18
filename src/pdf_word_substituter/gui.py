"""Simple window for replacing or removing text in a PDF.

Run with:  uv run pdf-word-substituter-gui
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .substitute import DEFAULT_FOLDER, parse_rules, replace_texts, summarize

PAD = 8


class RuleRow:
    """One "Find / Replace with" line in the changes list."""

    def __init__(self, app: "App", find: str = "", replace: str = ""):
        self.app = app
        self.find = tk.StringVar(value=find)
        self.replace = tk.StringVar(value=replace)
        parent = app.rules_frame
        self.find_entry = ttk.Entry(parent, textvariable=self.find, width=34)
        self.replace_entry = ttk.Entry(parent, textvariable=self.replace, width=34)
        self.delete_button = ttk.Button(
            parent, text="Remove", command=lambda: app.delete_row(self)
        )

    def grid(self, row: int) -> None:
        self.find_entry.grid(row=row, column=0, sticky="ew", padx=(0, PAD), pady=2)
        self.replace_entry.grid(row=row, column=1, sticky="ew", padx=(0, PAD), pady=2)
        self.delete_button.grid(row=row, column=2, pady=2)

    def destroy(self) -> None:
        for widget in (self.find_entry, self.replace_entry, self.delete_button):
            widget.destroy()


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("PDF Word Substituter")
        root.minsize(640, 480)

        self.pdf_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.ignore_case = tk.BooleanVar(value=False)
        self.auto_output = ""  # last output path we filled in ourselves
        self.rows: list[RuleRow] = []

        main = ttk.Frame(root, padding=PAD * 2)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        # PDF file
        ttk.Label(main, text="PDF file").grid(row=0, column=0, sticky="w")
        ttk.Entry(main, textvariable=self.pdf_path).grid(
            row=0, column=1, sticky="ew", padx=PAD
        )
        ttk.Button(main, text="Browse...", command=self.choose_pdf).grid(
            row=0, column=2
        )

        # Changes
        changes = ttk.LabelFrame(main, text="Changes", padding=PAD)
        changes.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=PAD * 2)
        main.rowconfigure(1, weight=1)
        changes.columnconfigure(0, weight=1)

        self.rules_frame = ttk.Frame(changes)
        self.rules_frame.grid(row=0, column=0, sticky="nsew")
        self.rules_frame.columnconfigure(0, weight=1)
        self.rules_frame.columnconfigure(1, weight=1)
        ttk.Label(self.rules_frame, text="Find (exact text)").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(self.rules_frame, text="Replace with (leave empty to remove)").grid(
            row=0, column=1, sticky="w"
        )

        buttons = ttk.Frame(changes)
        buttons.grid(row=1, column=0, sticky="w", pady=(PAD, 0))
        ttk.Button(buttons, text="+ Add change", command=self.add_row).pack(side="left")
        ttk.Button(
            buttons, text="Load rules file...", command=self.load_rules_file
        ).pack(side="left", padx=PAD)
        ttk.Checkbutton(
            buttons, text="Ignore capital letters", variable=self.ignore_case
        ).pack(side="left", padx=PAD)

        # Output file
        ttk.Label(main, text="Save as").grid(row=2, column=0, sticky="w")
        ttk.Entry(main, textvariable=self.output_path).grid(
            row=2, column=1, sticky="ew", padx=PAD
        )
        ttk.Button(main, text="Browse...", command=self.choose_output).grid(
            row=2, column=2
        )

        # Apply + result
        ttk.Button(main, text="Apply changes", command=self.apply).grid(
            row=3, column=0, columnspan=3, pady=PAD * 2
        )
        self.status = ttk.Label(main, text="")
        self.status.grid(row=4, column=0, columnspan=3, sticky="w")
        self.result = tk.Text(main, height=7, state="disabled", relief="flat")
        self.result.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(4, 0))

        self.add_row()

    # --- changes list -------------------------------------------------------

    def add_row(self, find: str = "", replace: str = "") -> None:
        row = RuleRow(self, find, replace)
        self.rows.append(row)
        row.grid(len(self.rows))
        row.find_entry.focus_set()

    def delete_row(self, row: RuleRow) -> None:
        if len(self.rows) == 1:
            row.find.set("")
            row.replace.set("")
            return
        self.rows.remove(row)
        row.destroy()
        for i, r in enumerate(self.rows, start=1):
            r.grid(i)

    def set_rules(self, rules: list[tuple[str, str]]) -> None:
        for row in self.rows:
            row.destroy()
        self.rows = []
        for find, replace in rules or [("", "")]:
            self.add_row(find, replace)

    def get_rules(self) -> list[tuple[str, str]]:
        return [(r.find.get(), r.replace.get()) for r in self.rows if r.find.get()]

    # --- files --------------------------------------------------------------

    def start_folder(self) -> str:
        current = Path(self.pdf_path.get()).parent
        if self.pdf_path.get() and current.is_dir():
            return str(current)
        return str(DEFAULT_FOLDER if DEFAULT_FOLDER.is_dir() else Path.home())

    def choose_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a PDF",
            initialdir=self.start_folder(),
            filetypes=[("PDF files", "*.pdf *.PDF"), ("All files", "*")],
        )
        if path:
            self.set_pdf(path)

    def set_pdf(self, path: str) -> None:
        self.pdf_path.set(path)
        # Suggest an output name, unless the user already typed their own
        if self.output_path.get() in ("", self.auto_output):
            p = Path(path)
            self.auto_output = str(p.with_name(f"{p.stem}_updated.pdf"))
            self.output_path.set(self.auto_output)

    def choose_output(self) -> None:
        current = Path(self.output_path.get() or self.pdf_path.get() or "result.pdf")
        path = filedialog.asksaveasfilename(
            title="Save the new PDF as",
            initialdir=self.start_folder(),
            initialfile=current.name,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if path:
            self.output_path.set(path)

    def load_rules_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a rules file",
            initialdir=self.start_folder(),
            filetypes=[("Text files", "*.txt"), ("All files", "*")],
        )
        if not path:
            return
        try:
            rules = parse_rules(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Couldn't read rules file", str(e))
            return
        if not rules:
            messagebox.showwarning("No rules", "That file has no rules in it.")
            return
        self.set_rules(rules)

    # --- run ----------------------------------------------------------------

    def apply(self) -> None:
        pdf = Path(self.pdf_path.get().strip())
        output = Path(self.output_path.get().strip())
        rules = self.get_rules()

        if not self.pdf_path.get().strip() or not pdf.is_file():
            messagebox.showerror("No PDF", "Choose the PDF file to change.")
            return
        if not rules:
            messagebox.showerror("No changes", "Type at least one text to find.")
            return
        if not self.output_path.get().strip():
            messagebox.showerror("No output", "Choose where to save the new PDF.")
            return

        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            counts, skipped = replace_texts(pdf, output, rules, self.ignore_case.get())
        except Exception as e:  # show any problem instead of failing silently
            messagebox.showerror("Something went wrong", str(e))
            return
        finally:
            self.root.config(cursor="")

        lines, missing = summarize(rules, counts, skipped)
        if not any(counts):
            self.show_result(
                "No text found. Nothing was saved. "
                "Check spelling, spaces and capital letters.",
                "red",
                lines,
            )
        elif missing:
            self.show_result(
                f"Saved {output.name}, but {missing} change(s) weren't found.",
                "#b36b00",
                lines,
            )
        else:
            self.show_result(f"Saved {output.name}", "green", lines)

    def show_result(self, message: str, color: str, lines: list[str]) -> None:
        self.status.config(text=message, foreground=color)
        self.result.config(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("end", "\n".join(lines))
        self.result.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    ttk.Style(root).theme_use("clam")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
