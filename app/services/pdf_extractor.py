import io
import logging
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# Unter diesem Schwellenwert pro Seite gilt die Seite als Scan-/Bild-PDF
_MIN_CHARS_PER_PAGE = 50
# OCR-Auflösung: 300 DPI ist Standard für gute Erkennungsrate
_OCR_DPI = 300
# Sprachen für Tesseract: Deutsch + Englisch
_OCR_LANG = "deu+eng"


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, bool]:
    """
    Extrahiert Text aus einem PDF.

    Strategie:
    1. Direkte Text-Extraktion via PyMuPDF (schnell, präzise)
    2. Seiten mit zu wenig Text → OCR-Fallback via Tesseract (für Scan-PDFs)

    Returns:
        tuple[str, bool]: (extrahierter Text, ocr_used)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    ocr_used = False

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()

        if len(text) < _MIN_CHARS_PER_PAGE:
            logger.info(f"Seite {page_num}: nur {len(text)} Zeichen extrahiert — OCR-Fallback")
            text = _ocr_page(page)
            ocr_used = True
        else:
            logger.debug(f"Seite {page_num}: {len(text)} Zeichen direkt extrahiert")

        pages.append(text)

    doc.close()

    full_text = "\n".join(pages)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    full_text = re.sub(r"[ \t]+", " ", full_text)
    return full_text.strip(), ocr_used


def _ocr_page(page: fitz.Page) -> str:
    """Rendert eine PDF-Seite als Bild und führt Tesseract-OCR durch."""
    pix = page.get_pixmap(dpi=_OCR_DPI)
    img_bytes = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_bytes))
    return pytesseract.image_to_string(image, lang=_OCR_LANG)
