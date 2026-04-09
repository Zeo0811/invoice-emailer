"""Chinese invoice parser using pdfplumber + rapidocr for text extraction, then regex parsing."""

import re
import io
import pdfplumber
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

ocr_engine = RapidOCR()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF. Try pdfplumber first, fall back to OCR for scanned PDFs."""
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"

    # If pdfplumber got meaningful text, use it
    if len(text.strip()) > 20:
        return text

    # Fall back to OCR for scanned PDFs
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=300).original
            text += _ocr_image(img) + "\n"

    return text


def extract_text_from_image(file_bytes: bytes) -> str:
    """Extract text from image using OCR."""
    img = Image.open(io.BytesIO(file_bytes))
    return _ocr_image(img)


def _ocr_image(img: Image.Image) -> str:
    """Run OCR on a PIL Image."""
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    result, _ = ocr_engine(img_bytes.getvalue())
    if not result:
        return ""
    return "\n".join([line[1] for line in result])


def parse_invoice_text(text: str) -> dict:
    """Parse date, amount, and seller name from invoice text using regex."""
    date = _extract_date(text)
    amount = _extract_amount(text)
    seller = _extract_seller(text)
    return {"date": date, "amount": amount, "seller": seller}


def _extract_date(text: str) -> str:
    """Extract invoice date."""
    # Pattern: 开票日期：2024年01月15日
    m = re.search(r"开票日期\s*[:：]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # Pattern: 开票日期 2024-01-15
    m = re.search(r"开票日期\s*[:：]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
    if m:
        return m.group(1).replace("/", "-")

    # Generic date: 2024年01月15日
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return "未知"


def _extract_amount(text: str) -> str:
    """Extract total amount (价税合计)."""
    # Pattern: 价税合计(小写) ¥1280.00 or ￥1280.00
    m = re.search(r"价\s*税\s*合\s*计\s*[\(（]?\s*小\s*写\s*[\)）]?\s*[¥￥]?\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")

    # Pattern: 小写 ¥1280.00
    m = re.search(r"小\s*写\s*[¥￥]\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")

    # Pattern: ¥1280.00 near 价税合计
    m = re.search(r"价\s*税\s*合\s*计[\s\S]{0,20}?[¥￥]\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")

    # Pattern: 合计金额 or 合 计
    m = re.search(r"[¥￥]\s*([\d,]+\.\d{2})", text)
    if m:
        return m.group(1).replace(",", "")

    return "未知"


def _extract_seller(text: str) -> str:
    """Extract seller name (销售方名称)."""
    # Pattern: 销售方 followed by 名称: XXX公司
    # Handle spaced characters like 销 售 方, 名 称
    m = re.search(r"销\s*售\s*方[\s\S]{0,30}?名\s*称\s*[:：]\s*(.+)", text)
    if m:
        name = m.group(1).strip()
        # Clean up: take until next field label or newline
        name = re.split(r"\s{2,}|纳税人识别号|统一社会信用代码|地\s*址|开户", name)[0].strip()
        if name:
            return name

    # Pattern: 销售方名称 on same line
    m = re.search(r"名\s*称\s*[:：]\s*(.+?)(?:\s{2,}|$)", text, re.MULTILINE)
    if m:
        # This might match buyer too, so look for it after "销售方" section
        # Find all 名称 matches and take the second one (first is buyer, second is seller)
        matches = re.findall(r"名\s*称\s*[:：]\s*(.+?)(?:\s{2,}|$)", text, re.MULTILINE)
        if len(matches) >= 2:
            name = matches[1].strip()
            name = re.split(r"纳税人|统一社会|地\s*址|开户", name)[0].strip()
            if name:
                return name

    return "未知"


def parse_invoice(file_bytes: bytes, content_type: str) -> dict:
    """Main entry: extract text from file, then parse invoice fields."""
    if content_type == "application/pdf":
        text = extract_text_from_pdf(file_bytes)
    else:
        text = extract_text_from_image(file_bytes)

    return parse_invoice_text(text)
