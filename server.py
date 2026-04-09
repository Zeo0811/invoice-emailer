import os
import hashlib
from pathlib import Path
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

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

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
<title>Invoice Emailer — 十字路口 Crossing</title>
<link rel="icon" href="/static/favicon.ico" type="image/x-icon">
<style>
  :root {
    --green: #407600;
    --green-dark: #356200;
    --green-light: #f4f9ed;
    --green-border: #c5e0a5;
    --dark: #1a1a1a;
    --gray: #666;
    --gray-light: #f7f7f7;
    --border: #e5e5e5;
    --radius: 8px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif;
    background: #f0f2f5; color: var(--dark); min-height: 100vh;
    display: flex; flex-direction: column;
  }

  /* Header */
  .header {
    height: 56px; position: sticky; top: 0; z-index: 100;
    background: linear-gradient(135deg, #356200, #407600, #4a8800);
    box-shadow: 0 2px 8px rgba(64,118,0,.2);
    padding: 0 24px; display: flex; align-items: center; gap: 12px;
    color: #fff;
  }
  .header img.logo { width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0; }
  .header h1 { font-size: 16px; font-weight: 700; }
  .header .tag {
    padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 500;
    background: rgba(255,255,255,.15); color: rgba(255,255,255,.85);
  }

  /* Main */
  .main {
    flex: 1; display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }

  /* Card */
  .card {
    background: #fff; border-radius: 12px; padding: 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
    max-width: 480px; width: 100%;
  }
  .card-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; color: var(--dark); }
  .card-subtitle { font-size: 14px; color: var(--gray); margin-bottom: 24px; }

  /* Label */
  .label {
    display: block; font-size: 12px; font-weight: 600; color: var(--gray);
    margin-bottom: 8px; text-transform: uppercase; letter-spacing: .5px;
  }

  /* Drop zone */
  .drop-zone {
    border: 2px dashed var(--border); border-radius: var(--radius);
    padding: 40px 20px; text-align: center; cursor: pointer;
    transition: all .2s;
  }
  .drop-zone:hover, .drop-zone.drag-over {
    border-color: var(--green-border); background: var(--green-light);
  }
  .drop-zone-icon { margin-bottom: 12px; color: var(--gray); }
  .drop-zone-icon svg { width: 40px; height: 40px; stroke: var(--green); opacity: .6; }
  .drop-zone p { color: var(--gray); font-size: 14px; }
  .drop-zone .hint { color: #aaa; font-size: 12px; margin-top: 6px; }
  .file-name {
    margin-top: 10px; font-size: 13px; font-weight: 500;
    color: var(--green); display: inline-flex; align-items: center; gap: 4px;
  }
  input[type="file"] { display: none; }

  /* Buttons */
  .btn {
    width: 100%; margin-top: 16px; padding: 14px;
    color: #fff; border: none; border-radius: var(--radius);
    font-size: 15px; font-weight: 600; cursor: pointer;
    transition: all .25s;
    display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  }
  .btn svg { width: 16px; height: 16px; }
  .btn-primary {
    background: linear-gradient(135deg, #407600, #4a8800);
    box-shadow: 0 2px 8px rgba(64,118,0,.25);
  }
  .btn-primary:hover {
    background: linear-gradient(135deg, #356200, #407600);
    box-shadow: 0 4px 20px rgba(64,118,0,.3);
    transform: translateY(-1px);
  }
  .btn-send {
    background: linear-gradient(135deg, #407600, #4a8800);
    box-shadow: 0 2px 8px rgba(64,118,0,.25);
  }
  .btn-send:hover {
    background: linear-gradient(135deg, #356200, #407600);
    box-shadow: 0 4px 20px rgba(64,118,0,.3);
    transform: translateY(-1px);
  }
  .btn:disabled {
    background: #ccc; box-shadow: none; cursor: not-allowed;
    transform: none;
  }

  /* Preview */
  .preview {
    margin-top: 20px; padding: 16px 20px; border-radius: 10px;
    font-size: 14px; line-height: 2;
    background: var(--green-light); border: 1px solid var(--green-border);
  }
  .preview .field-label { font-weight: 600; color: var(--gray); margin-right: 4px; }
  .preview .field-value { color: var(--dark); }
  .preview .subject-line {
    margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--green-border);
    font-size: 13px; color: var(--gray);
  }
  .preview .subject-line strong { color: var(--dark); font-weight: 600; }

  /* Status bar */
  .status {
    margin-top: 16px; padding: 12px 16px; border-radius: var(--radius);
    font-size: 13px; display: flex; align-items: center; gap: 8px;
  }
  .status svg { width: 16px; height: 16px; flex-shrink: 0; }
  .status.success { background: var(--green-light); color: var(--green); }
  .status.error { background: #fff0f0; color: #c00; }

  /* Spinner */
  .spinner {
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,.4); border-top-color: #fff;
    border-radius: 50%; animation: spin .6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hidden { display: none; }

  /* Mobile */
  @media (max-width: 640px) {
    .header { padding: 0 16px; }
    .main { padding: 16px; }
    .card { padding: 18px 16px; border-radius: 10px; }
    .card-title { font-size: 19px; }
    .btn { font-size: 16px; }
    .drop-zone { padding: 32px 16px; }
  }
</style>
</head>
<body>

<div class="header">
  <img class="logo" src="/static/logo.png" alt="十字路口">
  <h1>Invoice Emailer</h1>
  <span class="tag">Crossing Tools</span>
</div>

<div class="main">
<div class="card">
  <h2 class="card-title">发票解析 & 发送</h2>
  <p class="card-subtitle">上传发票文件，预览解析结果，确认后发送到邮箱</p>

  <span class="label">上传发票</span>
  <div class="drop-zone" id="dropZone">
    <div class="drop-zone-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
    </div>
    <p>点击或拖拽发票文件到此处</p>
    <p class="hint">支持 PDF / PNG / JPG / WEBP，最大 10MB</p>
    <p class="file-name hidden" id="fileName"></p>
  </div>
  <input type="file" id="fileInput" accept=".pdf,.png,.jpg,.jpeg,.webp">

  <button class="btn btn-primary" id="parseBtn" disabled>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    解析发票
  </button>

  <div class="preview hidden" id="preview">
    <div><span class="field-label">开票日期</span><span class="field-value" id="pDate"></span></div>
    <div><span class="field-label">价税合计</span><span class="field-value" id="pAmount"></span> 元</div>
    <div><span class="field-label">销售方</span><span class="field-value" id="pSeller"></span></div>
    <div class="subject-line">邮件主题：<strong id="pSubject"></strong></div>
    <button class="btn btn-send" id="sendBtn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      确认发送邮件
    </button>
  </div>

  <div class="status hidden" id="result"></div>
</div>
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
  fileName.classList.remove('hidden');
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
      document.getElementById('pSubject').textContent = data.invoice.date + ' ' + data.invoice.amount + '元 ' + data.invoice.seller;
      pendingToken = data.token;
      preview.classList.remove('hidden');
    } else {
      showError(data.detail || '解析失败');
    }
  } catch (e) {
    showError('网络错误：' + e.message);
  }
  parseBtn.disabled = false;
  parseBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>解析发票';
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
      result.className = 'status success';
      result.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>发送成功！邮件主题：' + data.email.subject;
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
  sendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>确认发送邮件';
});

function showError(msg) {
  result.className = 'status error';
  result.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>' + msg;
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
