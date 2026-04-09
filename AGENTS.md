# Invoice Emailer - Agent Integration

## Overview

Upload a Chinese invoice file (PDF or image), the service automatically extracts date, amount, and seller name via OCR, then sends the invoice as an email attachment.

## Endpoint

```
POST {BASE_URL}/api/send-invoice
Content-Type: multipart/form-data
```

## Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invoice` | file | Yes | Invoice file. Accepted: PDF, PNG, JPG, JPEG, WEBP. Max 10MB. |

## Response

### Success (200)

```json
{
  "success": true,
  "invoice": {
    "date": "2024-01-15",
    "amount": "1280.00",
    "seller": "某某科技有限公司"
  },
  "email": {
    "id": "email_xxx",
    "to": "zeo0811@gmail.com",
    "subject": "2024-01-15 1280.00元 某某科技有限公司"
  }
}
```

### Error (400 / 500)

```json
{
  "detail": "Error description"
}
```

## Rules

1. Field name MUST be `invoice`.
2. Send one invoice per request. For multiple invoices, call sequentially.
3. Timeout: recommend 60s (OCR may be slow).
4. NOT idempotent: duplicate uploads send duplicate emails. Avoid re-calling.
5. No authentication required. No recipient parameter needed.

## Agent Workflow

```
1. User provides an invoice file path
2. Verify the file exists and format is supported (PDF/PNG/JPG/JPEG/WEBP)
3. POST /api/send-invoice with the file as "invoice" field (multipart/form-data)
4. Check response: success == true
5. Report parsed invoice info (date, amount, seller) and email status to user
```

## cURL Example

```bash
curl -X POST https://your-app.railway.app/api/send-invoice \
  -F "invoice=@/path/to/invoice.pdf"
```

## Health Check

```
GET {BASE_URL}/api/health → {"status": "ok"}
```
