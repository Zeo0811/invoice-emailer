const express = require("express");
const multer = require("multer");
const { Resend } = require("resend");
const Anthropic = require("@anthropic-ai/sdk");
const path = require("path");
const fs = require("fs");

const app = express();
app.use(express.json());

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const allowed = [".pdf", ".png", ".jpg", ".jpeg", ".webp"];
    const ext = path.extname(file.originalname).toLowerCase();
    if (allowed.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error("Only PDF and image files (png/jpg/jpeg/webp) are allowed"));
    }
  },
});

const resend = new Resend(process.env.RESEND_API_KEY);
const anthropic = new Anthropic();

const RECIPIENT_EMAIL = process.env.RECIPIENT_EMAIL || "zeo0811@gmail.com";

async function parseInvoice(fileBuffer, mimeType) {
  const base64 = fileBuffer.toString("base64");

  const isPdf = mimeType === "application/pdf";
  const content = isPdf
    ? [
        {
          type: "document",
          source: { type: "base64", media_type: "application/pdf", data: base64 },
        },
        {
          type: "text",
          text: `请从这张发票中提取以下信息，以JSON格式返回（不要markdown代码块）：
{
  "date": "开票日期，格式 YYYY-MM-DD",
  "amount": "价税合计金额（含税总额），纯数字字符串",
  "seller": "销售方名称"
}
如果某个字段无法识别，用 "未知" 填充。只返回JSON，不要其他内容。`,
        },
      ]
    : [
        {
          type: "image",
          source: { type: "base64", media_type: mimeType, data: base64 },
        },
        {
          type: "text",
          text: `请从这张发票中提取以下信息，以JSON格式返回（不要markdown代码块）：
{
  "date": "开票日期，格式 YYYY-MM-DD",
  "amount": "价税合计金额（含税总额），纯数字字符串",
  "seller": "销售方名称"
}
如果某个字段无法识别，用 "未知" 填充。只返回JSON，不要其他内容。`,
        },
      ];

  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1024,
    messages: [{ role: "user", content }],
  });

  const text = response.content[0].text.trim();
  try {
    return JSON.parse(text);
  } catch {
    // Try to extract JSON from the response
    const match = text.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error(`Failed to parse invoice info: ${text}`);
  }
}

async function sendInvoiceEmail(invoiceInfo, fileBuffer, originalName, mimeType) {
  const subject = `${invoiceInfo.date} ${invoiceInfo.amount}元 ${invoiceInfo.seller}`;

  const { data, error } = await resend.emails.send({
    from: "Invoice Bot <onboarding@resend.dev>",
    to: [RECIPIENT_EMAIL],
    subject,
    html: `
      <h2>发票信息</h2>
      <table style="border-collapse:collapse;font-size:15px;">
        <tr><td style="padding:6px 12px;font-weight:bold;">开票日期</td><td style="padding:6px 12px;">${invoiceInfo.date}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:bold;">金额</td><td style="padding:6px 12px;">${invoiceInfo.amount} 元</td></tr>
        <tr><td style="padding:6px 12px;font-weight:bold;">销售方</td><td style="padding:6px 12px;">${invoiceInfo.seller}</td></tr>
      </table>
      <p style="color:#888;margin-top:20px;">此邮件由 Invoice Emailer 自动发送</p>
    `,
    attachments: [
      {
        filename: originalName,
        content: fileBuffer,
        content_type: mimeType,
      },
    ],
  });

  if (error) throw new Error(`Resend error: ${JSON.stringify(error)}`);
  return data;
}

// Health check
app.get("/", (req, res) => {
  res.json({
    service: "invoice-emailer",
    version: "1.0.0",
    endpoints: {
      "POST /api/send-invoice": "Upload an invoice file and send it via email",
      "GET /api/health": "Health check",
    },
  });
});

app.get("/api/health", (req, res) => {
  res.json({ status: "ok" });
});

// Main endpoint: upload invoice and send email
app.post("/api/send-invoice", upload.single("invoice"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No invoice file uploaded. Use field name 'invoice'." });
    }

    const mimeType = req.file.mimetype;
    const fileBuffer = req.file.buffer;
    const originalName = req.file.originalname;

    // Step 1: Parse invoice with Claude
    const invoiceInfo = await parseInvoice(fileBuffer, mimeType);

    // Step 2: Send email via Resend
    const emailResult = await sendInvoiceEmail(invoiceInfo, fileBuffer, originalName, mimeType);

    res.json({
      success: true,
      invoice: invoiceInfo,
      email: {
        id: emailResult.id,
        to: RECIPIENT_EMAIL,
        subject: `${invoiceInfo.date} ${invoiceInfo.amount}元 ${invoiceInfo.seller}`,
      },
    });
  } catch (err) {
    console.error("Error:", err);
    res.status(500).json({ error: err.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Invoice Emailer running on port ${PORT}`);
});
