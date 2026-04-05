# Webhook Mode Configuration Guide

## Overview

The bot supports two modes of operation:
- **Polling Mode** (default) - Bot continuously asks Telegram for updates
- **Webhook Mode** (production) - Telegram sends updates to your bot via HTTPS

Webhook mode is **recommended for production** as it's more efficient and reliable.

---

## Polling Mode (Default)

No additional configuration needed. Just run:

```bash
python bot.py
```

**Best for:**
- Local development
- Testing
- Low-traffic bots

---

## Webhook Mode (Production)

### Requirements

1. **Public HTTPS URL** - Your bot must be accessible via HTTPS
2. **Domain or Subdomain** - e.g., `your-bot.railway.app`
3. **Port 8080** exposed (or custom port via `WEBHOOK_PORT`)

### Configuration

Add these environment variables to your `.env`:

```env
# Enable webhook mode
WEBHOOK_URL=https://your-bot.railway.app/webhook
WEBHOOK_SECRET=your_random_secret_token_here
WEBHOOK_PATH=/webhook
WEBHOOK_PORT=8080
WEBHOOK_HOST=0.0.0.0
```

### Variable Descriptions

| Variable | Required | Description |
|----------|----------|-------------|
| `WEBHOOK_URL` | **Yes** | Full HTTPS URL where Telegram will send updates |
| `WEBHOOK_SECRET` | Recommended | Secret token for webhook verification |
| `WEBHOOK_PATH` | No | URL path for webhook (default: `/webhook`) |
| `WEBHOOK_PORT` | No | Port to listen on (default: `8080`) |
| `WEBHOOK_HOST` | No | Host to bind (default: `0.0.0.0`) |

---

## PaaS Deployment Examples

### Railway

1. Deploy your bot on Railway
2. Railway provides: `https://your-project.railway.app`
3. Set environment variables:
   ```
   WEBHOOK_URL=https://your-project.railway.app/webhook
   WEBHOOK_SECRET=<generate random string>
   ```
4. Deploy - Railway automatically exposes port 8080

### Render

1. Create Web Service
2. Render provides: `https://your-project.onrender.com`
3. Set environment variables:
   ```
   WEBHOOK_URL=https://your-project.onrender.com/webhook
   WEBHOOK_SECRET=<generate random string>
   ```
4. Add port mapping in Render dashboard (8080)

### Fly.io

1. Deploy with `fly launch`
2. Fly.io provides: `https://your-app.fly.dev`
3. Set secrets:
   ```bash
   fly secrets set WEBHOOK_URL=https://your-app.fly.dev/webhook
   fly secrets set WEBHOOK_SECRET=<generate random string>
   ```
4. Ensure `fly.toml` exposes port 8080:
   ```toml
   [[services]]
     internal_port = 8080
     protocol = "tcp"
   ```

### Heroku

1. Deploy to Heroku
2. Heroku provides: `https://your-app.herokuapp.com`
3. Set config vars:
   ```bash
   heroku config:set WEBHOOK_URL=https://your-app.herokuapp.com/webhook
   heroku config:set WEBHOOK_SECRET=<generate random string>
   ```

---

## Generating a Secret Token

Generate a random secret token:

```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# Linux/Mac
openssl rand -hex 32

# PowerShell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
```

---

## How It Works

### Startup Flow (Webhook Mode)

```
1. Bot starts
2. Sets webhook URL via Telegram API
3. Starts aiohttp server on port 8080
4. Listens for POST /webhook requests
5. Telegram sends updates to your URL
6. Bot processes updates and responds
```

### Update Flow

```
User sends message
    ↓
Telegram API
    ↓
POST https://your-bot.com/webhook
    ↓
aiohttp server (port 8080)
    ↓
aiogram dispatcher
    ↓
Handler processes
    ↓
Response sent to user
```

---

## Health Checks

When webhook mode is enabled, these endpoints are available:

- `GET /` - Simple health check (returns "OK")
- `GET /health` - Detailed health check (returns system status)

Test locally:
```bash
curl http://localhost:8080/health
```

---

## Switching Between Modes

### Polling → Webhook

1. Add `WEBHOOK_URL` and `WEBHOOK_SECRET` to `.env`
2. Restart bot
3. Bot automatically sets webhook and starts HTTP server

### Webhook → Polling

1. Remove `WEBHOOK_URL` from `.env` (or set to empty)
2. Restart bot
3. Bot deletes webhook and starts polling

---

## Troubleshooting

### "Webhook not set" error

**Problem:** Bot starts but doesn't receive updates

**Solution:**
1. Verify `WEBHOOK_URL` is correct and HTTPS
2. Check that port 8080 is exposed in your PaaS
3. Verify domain is accessible from internet

**Test:**
```bash
curl https://your-bot.com/webhook
# Should return 405 Method Not Allowed (POST only)
```

### "Port already in use" error

**Problem:** Bot fails to start with "Address already in use"

**Solution:**
1. Check if another process is using port 8080
2. Change `WEBHOOK_PORT` to another port (e.g., 8081)
3. Update port mapping in PaaS

### "SSL error" or "Certificate verify failed"

**Problem:** Webhook URL uses HTTP instead of HTTPS

**Solution:**
- Telegram **requires** HTTPS for webhooks
- Ensure your PaaS provides automatic HTTPS (Railway, Render, Fly.io do)
- Don't use HTTP URLs

---

## Security Best Practices

1. **Always use WEBHOOK_SECRET** - Prevents unauthorized requests
2. **Use HTTPS only** - Telegram enforces this anyway
3. **Keep webhook URL private** - Don't commit to git
4. **Rotate secret periodically** - Good security hygiene
5. **Monitor webhook logs** - Watch for suspicious activity

---

## Performance Comparison

| Metric | Polling | Webhook |
|--------|---------|---------|
| **Latency** | 1-3 seconds | < 1 second |
| **API Calls** | 30-60/min | 0 (event-driven) |
| **Reliability** | Good | Excellent |
| **Resource Usage** | Low | Very Low |
| **Setup Complexity** | Simple | Moderate |

---

## Migration Checklist

- [ ] Obtain public HTTPS URL from PaaS
- [ ] Generate webhook secret token
- [ ] Add environment variables to `.env`
- [ ] Expose port 8080 in PaaS configuration
- [ ] Deploy and monitor logs
- [ ] Test bot responds to messages
- [ ] Verify health check endpoint works
- [ ] Remove old webhook URL (if switching from another bot)

---

## Example .env for Webhook Mode

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_key
ENCRYPTION_KEY=your_encryption_key

# Webhook Configuration
WEBHOOK_URL=https://your-bot.railway.app/webhook
WEBHOOK_SECRET=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# Optional (defaults shown)
WEBHOOK_PATH=/webhook
WEBHOOK_PORT=8080
WEBHOOK_HOST=0.0.0.0

# Your other settings...
ADMIN_IDS=123456789
CRYPTO_ADDRESS_USDT=...
```

---

**Last Updated:** 2026-04-05  
**Version:** 1.0
