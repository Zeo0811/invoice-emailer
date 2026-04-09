# Invoice Emailer

上传发票文件（PDF/图片），自动 OCR 解析发票信息（日期、金额、销售方），通过 Resend 发送到指定邮箱。

邮件主题格式：`2024-01-15 1280.00元 某某科技有限公司`

## 功能

- 支持 PDF（电子发票）和图片（PNG/JPG/WEBP）扫描件
- pdfplumber 提取 PDF 文字，rapidocr 处理扫描件 OCR
- 正则解析中国增值税发票标准字段
- 发票作为附件发送到邮箱
- 提供 Web 页面和 API 两种使用方式

## 部署

### Railway

1. Fork 或连接此仓库到 [Railway](https://railway.app)
2. 设置环境变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `RESEND_API_KEY` | 是 | [Resend](https://resend.com) API Key |
| `RECIPIENT_EMAIL` | 否 | 收件邮箱，默认 `zeo0811@gmail.com` |

3. Railway 自动构建部署（使用 Dockerfile）

### 本地运行

```bash
pip install -r requirements.txt

export RESEND_API_KEY=re_xxxx
export RECIPIENT_EMAIL=your@email.com

uvicorn server:app --reload
```

访问 `http://localhost:8000` 打开上传页面。

---

## API 文档

### `GET /`

返回发票上传 Web 页面。

### `GET /api/health`

健康检查。

```json
{"status": "ok"}
```

### `POST /api/send-invoice`

上传发票文件，解析并发送邮件。

**请求**

```
Content-Type: multipart/form-data
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `invoice` | file | 是 | 发票文件，支持 PDF/PNG/JPG/JPEG/WEBP，最大 10MB |

**cURL 示例**

```bash
curl -X POST https://your-app.railway.app/api/send-invoice \
  -F "invoice=@/path/to/invoice.pdf"
```

**成功响应** `200`

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

**错误响应** `400` / `500`

```json
{
  "detail": "错误描述"
}
```

---

## Agent 调用规则

本服务开放 API 供 AI Agent 调用。调用时遵循以下规则：

### 接入方式

Agent 通过 `POST /api/send-invoice` 接口上传发票文件（multipart/form-data），服务端自动完成解析和邮件发送。

### 调用规则

1. **文件字段名必须为 `invoice`**
2. **一次只发送一张发票**。多张发票需逐一调用
3. **支持格式**：PDF、PNG、JPG、JPEG、WEBP
4. **文件大小上限 10MB**
5. **不需要认证**，不需要传收件人地址（服务端已配置）
6. **超时建议 60 秒**（OCR 解析可能较慢）
7. **非幂等**：同一发票多次上传会发送多封邮件，Agent 应避免重复调用

### Agent 调用流程

```
1. 用户提供发票文件路径
2. Agent 确认文件存在且格式支持
3. Agent 调用 POST /api/send-invoice，将文件作为 invoice 字段上传
4. 检查响应中 success 是否为 true
5. 向用户展示解析结果（日期、金额、销售方）和发送状态
```

### 错误处理

| HTTP 状态码 | 含义 | Agent 应对 |
|-------------|------|-----------|
| 200 | 成功 | 展示结果 |
| 400 | 文件格式不支持或过大 | 提示用户更换文件 |
| 500 | 解析失败或邮件发送失败 | 提示用户重试或检查文件清晰度 |

### Claude Code MCP 工具调用示例

```json
{
  "tool": "send-invoice",
  "method": "POST",
  "url": "{BASE_URL}/api/send-invoice",
  "body": {
    "type": "multipart/form-data",
    "fields": {
      "invoice": "@/path/to/invoice.pdf"
    }
  }
}
```
