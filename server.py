import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import resend

from parser import parse_invoice

app = FastAPI(
    title="Invoice Emailer",
    version="1.0.0",
    description="Upload invoices, parse with OCR, send via email",
)

resend.api_key = os.environ.get("RESEND_API_KEY", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "zeo0811@gmail.com")

ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}

UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Invoice Emailer</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .container { background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 40px; max-width: 480px; width: 90%; }
  h1 { font-size: 22px; margin-bottom: 6px; }
  .subtitle { color: #888; font-size: 14px; margin-bottom: 28px; }
  .drop-zone { border: 2px dashed #ccc; border-radius: 8px; padding: 40px 20px; text-align: center; cursor: pointer; transition: all 0.2s; }
  .drop-zone:hover, .drop-zone.drag-over { border-color: #4f46e5; background: #f8f7ff; }
  .drop-zone p { color: #666; font-size: 15px; }
  .drop-zone .hint { color: #aaa; font-size: 12px; margin-top: 8px; }
  .file-name { margin-top: 12px; font-size: 14px; color: #4f46e5; font-weight: 500; }
  input[type="file"] { display: none; }
  button { width: 100%; margin-top: 20px; padding: 12px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; transition: background 0.2s; }
  button:hover { background: #4338ca; }
  button:disabled { background: #ccc; cursor: not-allowed; }
  .result { margin-top: 20px; padding: 16px; border-radius: 8px; font-size: 14px; line-height: 1.6; }
  .result.success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
  .result.error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
  .result .label { font-weight: 600; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 6px; vertical-align: middle; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <h1>Invoice Emailer</h1>
  <p class="subtitle">上传发票，自动解析并发送到邮箱</p>
  <div class="drop-zone" id="dropZone">
    <p>点击或拖拽发票文件到此处</p>
    <p class="hint">支持 PDF / PNG / JPG / WEBP，最大 10MB</p>
    <p class="file-name" id="fileName"></p>
  </div>
  <input type="file" id="fileInput" accept=".pdf,.png,.jpg,.jpeg,.webp">
  <button id="submitBtn" disabled>发送发票</button>
  <div class="result" id="result" style="display:none;"></div>
</div>
<script>
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const submitBtn = document.getElementById('submitBtn');
const result = document.getElementById('result');
let selectedFile = null;

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files.length) selectFile(fileInput.files[0]); });

function selectFile(file) {
  selectedFile = file;
  fileName.textContent = file.name;
  submitBtn.disabled = false;
  result.style.display = 'none';
}

submitBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span>解析发送中...';
  result.style.display = 'none';
  const form = new FormData();
  form.append('invoice', selectedFile);
  try {
    const res = await fetch('/api/send-invoice', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok && data.success) {
      result.className = 'result success';
      result.innerHTML = `<span class="label">发送成功</span><br>开票日期：${data.invoice.date}<br>金额：${data.invoice.amount} 元<br>销售方：${data.invoice.seller}<br>邮件主题：${data.email.subject}`;
    } else {
      result.className = 'result error';
      result.textContent = data.detail || data.error || '发送失败';
    }
  } catch (e) {
    result.className = 'result error';
    result.textContent = '网络错误：' + e.message;
  }
  result.style.display = 'block';
  submitBtn.disabled = false;
  submitBtn.textContent = '发送发票';
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return UPLOAD_PAGE


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
