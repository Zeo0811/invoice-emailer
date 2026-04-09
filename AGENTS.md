# Invoice Emailer - Agent 调用规则

## 服务说明

上传发票文件（PDF/图片），自动解析发票信息（日期、金额、销售方），通过邮件发送到指定邮箱。

## API Endpoint

```
POST {BASE_URL}/api/send-invoice
Content-Type: multipart/form-data
```

## 调用方式

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| invoice | file | 是 | 发票文件，支持 PDF/PNG/JPG/JPEG/WEBP，最大 10MB |

### 成功响应 (200)

```json
{
  "success": true,
  "invoice": {
    "date": "2026-04-08",
    "amount": "1280.00",
    "seller": "某某科技有限公司"
  },
  "email": {
    "id": "email_id",
    "to": "zeo0811@gmail.com",
    "subject": "2026-04-08 1280.00元 某某科技有限公司"
  }
}
```

### 错误响应

```json
{
  "error": "错误描述"
}
```

常见错误码：
- `400` - 未上传文件或文件格式不支持
- `500` - 解析失败或邮件发送失败

## Agent 调用示例

### cURL

```bash
curl -X POST {BASE_URL}/api/send-invoice \
  -F "invoice=@/path/to/invoice.pdf"
```

### Claude Code MCP Tool Use

当用户提供发票文件时，Agent 应：

1. 确认文件存在且格式支持（PDF/PNG/JPG/JPEG/WEBP）
2. 调用 `POST /api/send-invoice`，将文件作为 `invoice` 字段上传
3. 向用户确认发送结果，展示解析出的发票信息

### 调用规则

1. **一次只发送一张发票**。如果用户提供多张发票，逐一调用。
2. **文件大小不超过 10MB**。
3. **不需要额外参数**，收件人地址已在服务端配置。
4. **幂等性**：同一张发票多次上传会发送多封邮件，Agent 应避免重复调用。
5. **超时设置**：建议 30 秒超时（AI 解析需要时间）。

## 健康检查

```
GET {BASE_URL}/api/health
→ {"status": "ok"}
```
