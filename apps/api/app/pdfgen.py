from __future__ import annotations

from fpdf import FPDF


class LetterPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, "Legalo draft - not a filing, not legal advice. Review before you send.", align="C")


def html_to_pdf(plain: str, title: str) -> bytes:
    pdf = LetterPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, title)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    # fpdf2 latin-1 by default; transliterate unknown glyphs.
    safe = (
        plain.replace("₹", "Rs ")
        .replace("—", "-")
        .replace("–", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )
    pdf.multi_cell(0, 6, safe)
    return bytes(pdf.output())
