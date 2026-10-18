import fitz  # PyMuPDF

file_name = "Flavia Pilates Octubre 2026"
pdf_path = f"/mnt/c/Users/jnahu/Downloads/{file_name}.pdf"
new_file_name = "Flavia Pilates Octubre 2026_updated"
output_path = f"/mnt/c/Users/jnahu/Downloads/{new_file_name}.pdf"

text_to_replace = "Saldo de la cta cte: ARS -35.344.754,00"
replacement_text = ""  # empty = remove the text completely

doc = fitz.open(pdf_path)

# Default values
font_name = "helv"
font_size = 8
x_offset = 0
y_offset = 6


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


for page in doc:
    text_instances = page.search_for(text_to_replace)

    # Blank replacement: delete the text from the PDF instead of covering it,
    # so it can't be selected or copied afterwards.
    if not replacement_text:
        for inst in text_instances:
            page.add_redact_annot(inst, fill=(1, 1, 1))
        page.apply_redactions()
        continue

    for inst in text_instances:
        rect = fitz.Rect(inst)

        detected_font_name = "helv"
        detected_font_size = 8

        text_info = page.get_text("dict")
        found = False

        for block in text_info["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if text_to_replace in span["text"]:
                        detected_font_name = span["font"]
                        detected_font_size = span["size"]
                        found = True
                        break
                if found:
                    break
            if found:
                break

        # Erase old text
        erase_top = 0
        erase_bottom = 2
        erase_left = 0
        erase_right = 0

        erase_rect = fitz.Rect(
            rect.x0 + erase_left,
            rect.y0 + erase_top,
            rect.x1 - erase_right,
            rect.y1 - erase_bottom,
        )
        page.draw_rect(erase_rect, color=(1, 1, 1), fill=(1, 1, 1))

        # Try to preserve the original style as much as possible
        font_name = choose_fallback_font(detected_font_name)
        font_size = detected_font_size

        print(f"Detected PDF font: {detected_font_name} -> Using: {font_name}")

        x, y = inst[:2]
        page.insert_text(
            (x + x_offset, y + y_offset),
            replacement_text,
            fontsize=font_size,
            fontname=font_name,
            color=(0, 0, 0),
        )

# garbage=4 drops unused objects (like the old, pre-redaction page content),
# otherwise removed text can still be recovered from the file.
doc.save(output_path, garbage=4, deflate=True, clean=True)
doc.close()

print(f"Text replacement completed. Updated PDF saved as {output_path}")
