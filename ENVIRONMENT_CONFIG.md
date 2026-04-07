# Environment Configuration Guide

This project supports environment-based configuration to automatically switch between **polling mode** (development) and **webhook mode** (production).

## Overview

| Environment | Mode | Use Case | Webhook Required |
|------------|------|----------|------------------|
| `development` | Polling | Local testing, development | ❌ No |
| `production` | Webhook | Production deployment | ✅ Yes |

## Quick Start

### Development Mode

1. Copy the development template:
   ```bash
   cp .env.development.example .env
   ```

2. Fill in your credentials (bot token, Supabase, etc.)

3. Run the bot:
   ```bash
   python bot.py
   ```

The bot will automatically start in **polling mode**, which is perfect for local development and testing.

### Production Mode

1. Copy the production template:
   ```bash
   cp .env.production.example .env
   ```

2. Fill in all required fields including:
   - `APP_ENV=production`
   - `WEBHOOK_URL=https://your-domain.com/webhook`
   - `WEBHOOK_SECRET=your_secure_secret`

3. Deploy to your hosting platform (Render, Railway, Fly.io, etc.)

The bot will start in **webhook mode** and listen for updates from Telegram.

## Configuration Variables

### Required Variables (All Environments)

```env
# Application Environment
APP_ENV=development  # or 'production'

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# Encryption
ENCRYPTION_KEY=your_fernet_key_here
```

### Webhook Variables (Required for Production)

```env
# Webhook Configuration
WEBHOOK_URL=https://your-domain.com/webhook
WEBHOOK_SECRET=your_random_secret_here
```

> **Note**: The webhook runs on the same port as the Flask webapp (`WEBAPP_PORT`, defaults to 5000).

### Optional Variables

```env
# Stripe (for card validation)
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_AMOUNT_CENTS=50

# BIN Lookup
BIN_LOOKUP_API_KEY=
BINSEARCH_API_KEY=
BINSEARCH_USER_ID=

# Rate Limiting
RATE_LIMIT_PER_HOUR=5
RATE_LIMIT_PER_DAY=20
STRIPE_ACCOUNT_DAILY_LIMIT=200

# Card Cooldown
CARD_COOLDOWN_HOURS=24

# Admin Configuration
ADMIN_IDS=123456789
ADMIN_CONTACT=@admin
```

## How It Works

The bot checks the `APP_ENV` environment variable on startup:

1. **If `APP_ENV=development`**:
   - Bot starts in **polling mode** by default
   - No webhook setup required
   - Bot actively asks Telegram for updates

2. **If `APP_ENV=production`**:
   - Bot **requires** webhook configuration
   - Validation fails if `WEBHOOK_URL` or `WEBHOOK_SECRET` is missing
   - Bot passively receives updates from Telegram via webhook

### Logic Flow

```python
if config.app_env == "production":
    if not (webhook_url and webhook_secret):
        raise ValueError("Webhook required for production")
    start_webhook_mode()
else:
    start_polling_mode()
```

## Environment Files

### `.env.example`
Generic template with all variables (placeholder values)

### `.env.development.example`
Optimized for local development:
- `APP_ENV=development`
- No webhook configuration needed
- Uses test Stripe keys (`pk_test_*`)

### `.env.production.example`
Optimized for production deployment:
- `APP_ENV=production`
- Webhook configuration required
- Uses live Stripe keys (`pk_live_*`)

## Deployment Examples

### Render

```yaml
# render.yaml
services:
  - type: web
    name: card-validator-bot
    env: python
    buildCommand: pip install -r requirements.txt && playwright install chromium
    startCommand: python bot.py
    envVars:
      - key: APP_ENV
        value: production
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: SUPABASE_URL
        sync: false
      # ... other variables
      - key: WEBHOOK_URL
        value: https://your-app.onrender.com/webhook
      - key: WEBHOOK_SECRET
        generateValue: true
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  bot:
    build: .
    env_file:
      - .env.production  # or .env.development
    ports:
      - "5000:5000"
    environment:
      - APP_ENV=production
      - WEBHOOK_URL=https://your-domain.com/webhook
      - WEBHOOK_SECRET=your_secret_here
```

### Railway

1. Import your GitHub repo
2. Add environment variables in Railway dashboard:
   - `APP_ENV=production`
   - `WEBHOOK_URL=https://your-app.railway.app/webhook`
   - `WEBHOOK_SECRET=<generate-random-string>`
3. Deploy automatically

## Validation

The bot validates configuration on startup:

### Development Mode Checks
- ✅ Required vars present (bot token, Supabase, encryption key)
- ✅ `APP_ENV` is valid value

### Production Mode Checks
- ✅ All development checks
- ✅ `WEBHOOK_URL` is set
- ✅ `WEBHOOK_SECRET` is set
- ✅ `APP_ENV` is valid value

If validation fails, the bot exits with an error message listing missing variables.

## Switching Environments

To switch from development to production:

1. Update your `.env` file:
   ```env
   APP_ENV=production
   WEBHOOK_URL=https://your-domain.com/webhook
   WEBHOOK_SECRET=new_secure_secret
   ```

2. Restart the bot

That's it! The bot will automatically switch modes.

## Troubleshooting

### Bot starts in polling mode even with APP_ENV=production

**Cause**: `WEBHOOK_URL` or `WEBHOOK_SECRET` is missing/empty

**Solution**: Ensure both variables are set in your `.env` file

### ValueError: Missing required environment variables

**Cause**: Required variables not set for the chosen environment

**Solution**: Check the error message and set the missing variables

### Webhook not receiving updates

**Cause**: Webhook URL not accessible or incorrect

**Solution**: 
1. Ensure your domain is publicly accessible
2. Test the URL: `https://your-domain.com/webhook` should return a response
3. Check firewall/port settings (default: 5000)

## Security Best Practices

1. **Never commit `.env` files** to git (they're in `.gitignore`)
2. **Use different secrets** for development and production
3. **Rotate `WEBHOOK_SECRET`** periodically in production
4. **Use HTTPS** for webhook URLs in production
5. **Generate strong encryption keys** for production

Generate a secure webhook secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Migration from Old Setup

If you were using the bot before this change:

### Old Way
- Manually set/unset `WEBHOOK_URL` to switch modes
- Easy to misconfigure

### New Way
- Set `APP_ENV=development` or `APP_ENV=production`
- Bot automatically validates and switches modes
- Production **requires** webhook (fails fast if missing)

### Migration Steps

1. Add `APP_ENV=development` to your existing `.env` file
2. (Optional) Update to the new `.env.example` template
3. Restart the bot

No other changes needed - backward compatible!
