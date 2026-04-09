import os
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import resend

from parser import parse_invoice

app = FastAPI(title="Invoice Emailer", version="1.0.0")

resend.api_key = os.environ.get("RESEND_API_KEY", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "zeo0811@gmail.com")

ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}


@app.get("/")
def index():
    return {
        "service": "invoice-emailer",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/send-invoice": "Upload an invoice file and send it via email",
            "GET /api/health": "Health check",
        },
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/send-invoice")
async def send_invoice(invoice: UploadFile = File(...)):
    if invoice.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {invoice.content_type}. Allowed: PDF, PNG, JPG, WEBP")

    file_bytes = await invoice.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 10MB.")

    # Parse invoice
    try:
        info = parse_invoice(file_bytes, invoice.content_type)
    except Exception as e:
        raise HTTPException(500, f"Invoice parsing failed: {str(e)}")

    # Send email
    subject = f"{info['date']} {info['amount']}元 {info['seller']}"
    try:
        email = resend.Emails.send({
            "from": "Invoice Bot <onboarding@resend.dev>",
            "to": [RECIPIENT_EMAIL],
            "subject": subject,
            "html": f"""
                <h2>发票信息</h2>
                <table style="border-collapse:collapse;font-size:15px;">
                    <tr><td style="padding:6px 12px;font-weight:bold;">开票日期</td><td style="padding:6px 12px;">{info['date']}</td></tr>
                    <tr><td style="padding:6px 12px;font-weight:bold;">金额</td><td style="padding:6px 12px;">{info['amount']} 元</td></tr>
                    <tr><td style="padding:6px 12px;font-weight:bold;">销售方</td><td style="padding:6px 12px;">{info['seller']}</td></tr>
                </table>
                <p style="color:#888;margin-top:20px;">此邮件由 Invoice Emailer 自动发送</p>
            """,
            "attachments": [
                {
                    "filename": invoice.filename,
                    "content": list(file_bytes),
                }
            ],
        })
    except Exception as e:
        raise HTTPException(500, f"Email send failed: {str(e)}")

    return {
        "success": True,
        "invoice": info,
        "email": {
            "id": email.get("id") if isinstance(email, dict) else getattr(email, "id", None),
            "to": RECIPIENT_EMAIL,
            "subject": subject,
        },
    }
