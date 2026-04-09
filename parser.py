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
    m = re.search(r"开票日期\s*[:：]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    m = re.search(r"开票日期\s*[:：]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
    if m:
        return m.group(1).replace("/", "-")

    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return "未知"


def _extract_amount(text: str) -> str:
    """Extract total amount (价税合计)."""
    # (小写)¥100000.00 or （小写）¥100000.00
    m = re.search(r"[\(（]\s*小\s*写\s*[\)）]\s*[¥￥]\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")

    # 价税合计 ... ¥1280.00
    m = re.search(r"价\s*税\s*合\s*计[\s\S]{0,30}?[¥￥]\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")

    # 小写 ¥1280.00
    m = re.search(r"小\s*写\s*[¥￥]\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")

    # Any ¥ amount
    m = re.search(r"[¥￥]\s*([\d,]+\.\d{2})", text)
    if m:
        return m.group(1).replace(",", "")

    return "未知"


def _extract_seller(text: str) -> str:
    """Extract seller name (销售方名称).

    pdfplumber often merges columns into one line, producing patterns like:
      "购 名称：买方公司 销 名称：卖方公司"
    or on separate lines:
      "销售方 ... 名称：卖方公司"
    """
    # Pattern 1: "销 名称：XXX" (pdfplumber merged columns)
    # Matches: 销 名称：唐河县计出有据营销策划工作室（个体工商户）
    m = re.search(r"销\s+名\s*称\s*[:：]\s*(.+?)(?:\s{2,}|$)", text, re.MULTILINE)
    if m:
        name = _clean_seller_name(m.group(1))
        if name:
            return name

    # Pattern 2: "销售方" followed by "名称：XXX" within ~50 chars
    m = re.search(r"销\s*售\s*方[\s\S]{0,50}?名\s*称\s*[:：]\s*(.+)", text)
    if m:
        name = _clean_seller_name(m.group(1))
        if name:
            return name

    # Pattern 3: Two "名称：" on the same line — second one is seller
    # e.g., "购...名称：买方 销...名称：卖方"
    line_matches = re.findall(r"名\s*称\s*[:：]\s*(.+?)(?:\s+销|\s+名\s*称|$)", text, re.MULTILINE)
    if not line_matches:
        line_matches = re.findall(r"名\s*称\s*[:：]\s*(.+?)(?:\s{2,}|$)", text, re.MULTILINE)
    if len(line_matches) >= 2:
        name = _clean_seller_name(line_matches[1])
        if name:
            return name

    return "未知"


def _clean_seller_name(raw: str) -> str:
    """Clean up extracted seller name by removing trailing fields."""
    name = raw.strip()
    name = re.split(r"\s{2,}|纳税人识别号|纳\s*税\s*人|统一社会信用代码|地\s*址|开户|电\s*话", name)[0].strip()
    # Remove leading/trailing junk characters
    name = re.sub(r"^[\s:：]+|[\s:：]+$", "", name)
    return name


def parse_invoice(file_bytes: bytes, content_type: str) -> dict:
    """Main entry: extract text from file, then parse invoice fields."""
    if content_type == "application/pdf":
        text = extract_text_from_pdf(file_bytes)
    else:
        text = extract_text_from_image(file_bytes)

    return parse_invoice_text(text)
