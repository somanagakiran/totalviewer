"""
pdf_parser.py
Extracts a rasterized page image, dimension-like text values, and vector
line segments from the first page of a PDF using PyMuPDF (fitz).

All coordinates in the output are normalised to [0, 1] relative to page size
so the frontend can map them onto any plane geometry without knowing PDF points.
"""

import base64
import re

import fitz  # PyMuPDF

# Matches standalone numeric values optionally followed by a unit abbreviation.
# Examples: "150", "3.5mm", "12.7 cm", '5"', "0.375 in"
_DIMENSION_RE = re.compile(
    r"^\s*\d+(\.\d+)?\s*(mm|cm|m|in|\")?\s*$",
    re.IGNORECASE,
)

# Resolution for rasterisation (dots per inch).
_DPI = 150
_SCALE = _DPI / 72.0  # fitz native unit is 1/72 inch


def parse_pdf(filepath: str) -> dict:
    """
    Parse the first page of a PDF file.

    Returns
    -------
    dict with keys:
        file_type           : "pdf"
        width               : page width in PDF points
        height              : page height in PDF points
        page_image_b64      : base64-encoded PNG of the rasterised page
        extracted_dimensions: list of {text, x, y} with normalised coords
        vector_lines        : list of {x1, y1, x2, y2} with normalised coords
    """
    doc = fitz.open(filepath)
    try:
        page = doc[0]
        pw = page.rect.width   # points
        ph = page.rect.height  # points

        # ------------------------------------------------------------------
        # 1. Rasterise
        # ------------------------------------------------------------------
        mat = fitz.Matrix(_SCALE, _SCALE)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        page_image_b64 = base64.b64encode(pix.tobytes("png")).decode()

        # ------------------------------------------------------------------
        # 2. Extract dimension-like text
        # ------------------------------------------------------------------
        extracted_dimensions = []
        for block in page.get_text("blocks"):
            # block = (x0, y0, x1, y1, text, block_no, block_type)
            x0, y0, x1, y1 = block[:4]
            raw_text = block[4] if len(block) > 4 else ""
            for line in raw_text.splitlines():
                stripped = line.strip()
                if stripped and _DIMENSION_RE.match(stripped):
                    extracted_dimensions.append({
                        "text": stripped,
                        "x": ((x0 + x1) / 2) / pw,
                        "y": ((y0 + y1) / 2) / ph,
                    })

        # ------------------------------------------------------------------
        # 3. Extract vector line segments
        # ------------------------------------------------------------------
        vector_lines = []
        for path in page.get_drawings():
            items = path.get("items", [])
            prev_pt = None
            for item in items:
                kind = item[0]

                if kind == "m":  # move_to — no line drawn
                    prev_pt = item[1]

                elif kind == "l" and prev_pt is not None:  # line_to
                    end_pt = item[1]
                    vector_lines.append({
                        "x1": prev_pt.x / pw,
                        "y1": prev_pt.y / ph,
                        "x2": end_pt.x / pw,
                        "y2": end_pt.y / ph,
                    })
                    prev_pt = end_pt

                elif kind == "c" and prev_pt is not None:  # cubic bezier
                    # Only record the endpoint; skip the control points.
                    end_pt = item[3]
                    prev_pt = end_pt

                elif kind == "re":  # axis-aligned rectangle
                    rect = item[1]
                    rx0, ry0 = rect.x0 / pw, rect.y0 / ph
                    rx1, ry1 = rect.x1 / pw, rect.y1 / ph
                    vector_lines.extend([
                        {"x1": rx0, "y1": ry0, "x2": rx1, "y2": ry0},
                        {"x1": rx1, "y1": ry0, "x2": rx1, "y2": ry1},
                        {"x1": rx1, "y1": ry1, "x2": rx0, "y2": ry1},
                        {"x1": rx0, "y1": ry1, "x2": rx0, "y2": ry0},
                    ])

        return {
            "file_type": "pdf",
            "width": pw,
            "height": ph,
            "page_image_b64": page_image_b64,
            "extracted_dimensions": extracted_dimensions,
            "vector_lines": vector_lines,
        }

    finally:
        doc.close()
