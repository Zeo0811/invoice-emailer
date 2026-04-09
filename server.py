import os
import hashlib
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
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

# Temporary store for parsed invoices awaiting confirmation
_pending = {}

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
  .btn { width: 100%; margin-top: 14px; padding: 12px; color: #fff; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; transition: background 0.2s; }
  .btn-parse { background: #4f46e5; }
  .btn-parse:hover { background: #4338ca; }
  .btn-send { background: #16a34a; }
  .btn-send:hover { background: #15803d; }
  .btn:disabled { background: #ccc; cursor: not-allowed; }
  .preview { margin-top: 20px; padding: 16px; border-radius: 8px; font-size: 14px; line-height: 1.8; background: #f8fafc; border: 1px solid #e2e8f0; }
  .preview .label { font-weight: 600; color: #475569; }
  .result { margin-top: 14px; padding: 16px; border-radius: 8px; font-size: 14px; line-height: 1.6; }
  .result.success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
  .result.error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 6px; vertical-align: middle; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hidden { display: none; }
</style>
</head>
<body>
<div class="container">
  <h1>Invoice Emailer</h1>
  <p class="subtitle">上传发票，预览解析结果，确认后发送邮件</p>

  <div class="drop-zone" id="dropZone">
    <p>点击或拖拽发票文件到此处</p>
    <p class="hint">支持 PDF / PNG / JPG / WEBP，最大 10MB</p>
    <p class="file-name" id="fileName"></p>
  </div>
  <input type="file" id="fileInput" accept=".pdf,.png,.jpg,.jpeg,.webp">

  <button class="btn btn-parse" id="parseBtn" disabled>解析发票</button>

  <div class="preview hidden" id="preview">
    <div><span class="label">开票日期：</span><span id="pDate"></span></div>
    <div><span class="label">金额：</span><span id="pAmount"></span> 元</div>
    <div><span class="label">销售方：</span><span id="pSeller"></span></div>
    <div style="margin-top:8px;color:#888;font-size:13px;">邮件主题：<span id="pSubject"></span></div>
    <button class="btn btn-send" id="sendBtn">确认发送邮件</button>
  </div>

  <div class="result hidden" id="result"></div>
</div>

<script>
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const parseBtn = document.getElementById('parseBtn');
const preview = document.getElementById('preview');
const sendBtn = document.getElementById('sendBtn');
const result = document.getElementById('result');

let selectedFile = null;
let pendingToken = null;

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
  parseBtn.disabled = false;
  preview.classList.add('hidden');
  result.classList.add('hidden');
  pendingToken = null;
}

// Step 1: Parse only
parseBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  parseBtn.disabled = true;
  parseBtn.innerHTML = '<span class="spinner"></span>解析中...';
  preview.classList.add('hidden');
  result.classList.add('hidden');

  const form = new FormData();
  form.append('invoice', selectedFile);
  try {
    const res = await fetch('/api/parse-invoice', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      document.getElementById('pDate').textContent = data.invoice.date;
      document.getElementById('pAmount').textContent = data.invoice.amount;
      document.getElementById('pSeller').textContent = data.invoice.seller;
      document.getElementById('pSubject').textContent = `${data.invoice.date} ${data.invoice.amount}元 ${data.invoice.seller}`;
      pendingToken = data.token;
      preview.classList.remove('hidden');
    } else {
      showError(data.detail || '解析失败');
    }
  } catch (e) {
    showError('网络错误：' + e.message);
  }
  parseBtn.disabled = false;
  parseBtn.textContent = '解析发票';
});

// Step 2: Confirm and send
sendBtn.addEventListener('click', async () => {
  if (!pendingToken) return;
  sendBtn.disabled = true;
  sendBtn.innerHTML = '<span class="spinner"></span>发送中...';

  try {
    const res = await fetch('/api/confirm-send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: pendingToken }),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      result.className = 'result success';
      result.innerHTML = '发送成功！邮件主题：' + data.email.subject;
      result.classList.remove('hidden');
      preview.classList.add('hidden');
      pendingToken = null;
    } else {
      showError(data.detail || '发送失败');
    }
  } catch (e) {
    showError('网络错误：' + e.message);
  }
  sendBtn.disabled = false;
  sendBtn.textContent = '确认发送邮件';
});

function showError(msg) {
  result.className = 'result error';
  result.textContent = msg;
  result.classList.remove('hidden');
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return UPLOAD_PAGE


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/parse-invoice")
async def parse_invoice_endpoint(invoice: UploadFile = File(...)):
    """Step 1: Parse invoice and return preview. Does NOT send email."""
    if invoice.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {invoice.content_type}. Allowed: PDF, PNG, JPG, WEBP")

    file_bytes = await invoice.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 10MB.")

    try:
        info = parse_invoice(file_bytes, invoice.content_type)
    except Exception as e:
        raise HTTPException(500, f"Invoice parsing failed: {str(e)}")

    # Store for confirmation
    token = hashlib.sha256(file_bytes[:1024] + str(id(file_bytes)).encode()).hexdigest()[:16]
    _pending[token] = {
        "info": info,
        "file_bytes": file_bytes,
        "filename": invoice.filename,
        "content_type": invoice.content_type,
    }

    # Keep only last 20 pending items
    if len(_pending) > 20:
        oldest = list(_pending.keys())[0]
        del _pending[oldest]

    return {"invoice": info, "token": token}


@app.post("/api/confirm-send")
async def confirm_send(body: dict):
    """Step 2: Confirm and send the previously parsed invoice via email."""
    token = body.get("token")
    if not token or token not in _pending:
        raise HTTPException(400, "Invalid or expired token. Please re-upload the invoice.")

    data = _pending.pop(token)
    info = data["info"]
    file_bytes = data["file_bytes"]

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
                    "filename": data["filename"],
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


@app.post("/api/send-invoice")
async def send_invoice(invoice: UploadFile = File(...)):
    """One-step API for agents: parse + send in one call."""
    if invoice.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {invoice.content_type}. Allowed: PDF, PNG, JPG, WEBP")

    file_bytes = await invoice.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 10MB.")

    try:
        info = parse_invoice(file_bytes, invoice.content_type)
    except Exception as e:
        raise HTTPException(500, f"Invoice parsing failed: {str(e)}")

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
