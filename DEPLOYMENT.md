# Deployment Guide - Card Validator Bot

**Date:** 2026-04-06
**Status:** Ready for Production ✅

---

## Pre-Deployment Checklist

### ✅ Code is Ready
- [x] Stripe Elements + PaymentIntent validation (no SAQ D needed)
- [x] Full card data storage and export (JSON/CSV/TXT)
- [x] MarkdownV2 escaping throughout the bot
- [x] Proper slash commands (/validate, /balance, /plans, /history, /help, /quota)
- [x] Playwright browser automation for Stripe Elements
- [x] Flask webapp for Stripe Elements + PaymentIntent API
- [x] Graceful shutdown, log rotation, session timeout
- [x] Error handling & retry logic for all external calls
- [x] Country code to full name mapping (40+ countries)
- [x] Professional card validation result display

### ⚠️ Before Deploying - IMPORTANT

**You MUST add yourself to the database FIRST:**

Since admin checks are now **purely database-driven**, you need to ensure your Telegram ID is in the `admins` table before deploying.

Run this in **Supabase SQL Editor**:

```sql
-- Add yourself as super admin (replace with your actual details)
INSERT INTO admins (telegram_id, username, role, added_by)
VALUES (1151779389, 'your_username', 'super_admin', 0)
ON CONFLICT (telegram_id) DO UPDATE
SET role = 'super_admin', username = 'your_username';

-- Verify
SELECT telegram_id, username, role FROM admins;
```

---

## Database Migrations Required

Run these SQL files in Supabase SQL Editor **in order**:

### 1. Base Schema (if not already run)
```
database/migrations/001_initial_schema.sql
```

### 2. Settings Table (if not already run)
```
database/migrations/002_settings_table.sql
```

### 3. User Ban (if not already run)
```
database/migrations/003_user_ban.sql
```

### 4. Credit Transactions (if not already run)
```
database/migrations/004_credit_transactions.sql
```

### 5. Admins Table (REQUIRED)
```
database/migrations/005_admins_table.sql
```

### 6. Backups Table
```
database/migrations/003_add_backups_table.sql
```

### 7. Full Card Data Columns (NEW - REQUIRED for card exports)
```
database/migrations/006_add_full_card_columns.sql
```

**Quick Verification Query:**
```sql
-- Check if all tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'users', 'plans', 'stripe_accounts', 'validation_logs',
    'admin_logs', 'credit_transactions', 'card_cooldowns',
    'admins', 'backups', 'settings'
  )
ORDER BY table_name;
```

Should return **10 tables**.

---

## System Requirements

| Component | Requirement | Purpose |
|-----------|-------------|---------|
| **Python** | 3.11+ | Runtime |
| **Playwright** | Chromium browser | Stripe Elements automation |
| **Memory** | 512MB+ minimum | Bot + browser (~200MB) |
| **CPU** | 1 core+ | Processing |
| **Network** | Stable HTTPS | Telegram + Stripe + Supabase |

---

## Deployment Options

### Option 1: VPS / Dedicated Server (Recommended)

**Best for:** Full control, Playwright support, reliable uptime

**Step 1: Setup Server (Ubuntu/Debian)**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3 python3-pip python3-venv

# Install Playwright dependencies
sudo apt install -y \
  libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
  libgbm1 libasound2 libxshmfence1 libx11-xcb1
```

**Step 2: Clone & Setup**
```bash
git clone https://github.com/your-username/card_validator_bot.git
cd card_validator_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright Chromium
playwright install chromium

# Run setup script
chmod +x setup_elements.sh
./setup_elements.sh
```

**Step 3: Configure Environment**
```bash
cp .env.example .env
nano .env
# Add all variables (see Environment Variables section below)
```

**Step 4: Run with Systemd (auto-restart)**
```bash
sudo nano /etc/systemd/system/card-validator-bot.service
```

Add this content:
```ini
[Unit]
Description=Card Validator Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/card_validator_bot
ExecStart=/path/to/card_validator_bot/venv/bin/python bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable card-validator-bot
sudo systemctl start card-validator-bot

# Check status
sudo systemctl status card-validator-bot

# View logs
sudo journalctl -u card-validator-bot -f
```

---

### Option 2: Docker (Any VPS)

**Step 1: Setup VPS**
```bash
# SSH into VPS
ssh root@your-vps-ip

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**Step 2: Clone & Configure**
```bash
# Clone repo
git clone https://github.com/your-username/card_validator_bot.git
cd card_validator_bot

# Create .env file
nano .env
# Add all environment variables (see below)
```

**Step 3: Build Playwright Image**
The Dockerfile already includes Playwright Chromium installation.

**Step 4: Deploy**
```bash
# Build and run
docker compose up -d --build

# View logs
docker compose logs -f bot

# Stop
docker compose down
```

---

### Option 3: Railway (With Limitations)

⚠️ **Note:** Railway's ephemeral filesystem may not support Playwright well. Use VPS for reliable Stripe Elements automation.

If using Railway:
1. Add `playwright` and `flask` to `requirements.txt` (already included)
2. Add build step: `playwright install chromium`
3. Add all environment variables
4. Deploy

---

### Option 4: Render

⚠️ **Note:** Render's free tier sleeps after 15 minutes. Use paid tier for production.

1. Create Web Service
2. Build Command: `pip install -r requirements.txt && playwright install chromium`
3. Start Command: `python bot.py`
4. Add all environment variables
5. Deploy

---

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `123456:ABC-DEF...` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | `eyJhbGci...` |
| `ENCRYPTION_KEY` | Fernet encryption key | `kv1gWX-eoAq...` |
| `ADMIN_IDS` | Comma-separated admin IDs | `1151779389,123456789` |
| `CRYPTO_ADDRESS_USDT` | USDT TRC20 address | `TJYjBf3y...` |
| `CRYPTO_ADDRESS_BTC` | BTC address | `bc1q2gpw...` |
| `ADMIN_CONTACT` | Admin Telegram username | `@admin` |

### Stripe Variables (REQUIRED for validation)

| Variable | Description | Example |
|----------|-------------|---------|
| `STRIPE_PUBLISHABLE_KEY` | **Live** publishable key (for Stripe Elements) | `pk_live_51RrQQR...` |
| `STRIPE_AMOUNT_CENTS` | Authorization amount in cents | `50` ($0.50) |

⚠️ **Important:** The Stripe secret key is stored **encrypted in the database** (via admin panel). You must add a Stripe account through the bot's admin panel first.

### Webapp Variables (for Stripe Elements automation)

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBAPP_PORT` | `5000` | Flask webapp port (internal only) |
| `WEBAPP_URL` | `http://127.0.0.1:5000` | Webapp URL for Playwright |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_PER_HOUR` | `5` | Validations per hour per user |
| `RATE_LIMIT_PER_DAY` | `20` | Validations per day per user |
| `STRIPE_ACCOUNT_DAILY_LIMIT` | `200` | Stripe account daily limit |
| `CARD_COOLDOWN_HOURS` | `24` | Card cooldown period |
| `BIN_LOOKUP_API_KEY` | *(empty)* | BIN lookup API key |
| `BINSEARCH_API_KEY` | *(empty)* | binsearchlookup.com key |
| `BINSEARCH_USER_ID` | *(empty)* | binsearchlookup.com user ID |
| `OPENROUTER_API_KEY` | *(empty)* | OpenRouter AI API key |
| `WEBHOOK_URL` | *(empty)* | Webhook URL (for production) |
| `WEBHOOK_SECRET` | *(empty)* | Webhook secret token |
| `WEBHOOK_PATH` | `/webhook` | Webhook path |
| `WEBHOOK_PORT` | `8080` | Webhook port |
| `WEBHOOK_HOST` | `0.0.0.0` | Bind host |

---

## Setup Stripe for Elements Validation

### Step 1: Get Your Publishable Key
1. Go to: https://dashboard.stripe.com/apikeys
2. Copy your **live mode** publishable key (starts with `pk_live_`)
3. Add it to `.env` as `STRIPE_PUBLISHABLE_KEY`

### Step 2: Add Secret Key via Bot Admin Panel
1. Start the bot
2. Send `/admin` → Open Admin Panel
3. Click 🔑 Stripe → Add Account
4. Enter your **live secret key** (starts with `sk_live_`)
5. Activate the account

The bot will encrypt and store the secret key in the database. The webapp fetches it securely for PaymentIntent creation.

### Step 3: Enable Raw Card Data APIs (Optional but Recommended)
1. Go to: https://dashboard.stripe.com/account/integration/settings
2. Enable access to raw card data APIs
3. This allows full authorization checks without SAQ D compliance

---

## Generate Encryption Key

```python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Generate Webhook Secret (if using webhook)

```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Post-Deployment Verification

### 1. Check Bot is Running
```
Send /ping to bot
Should respond with: 🟢 Bot Status: Online
```

### 2. Verify Admin Access
```
Send /admin to bot
Should open Admin Panel (not "Admin only" error)
Should see "👑 Manage Admins" button (if super_admin)
```

### 3. Test User Commands
```
/send /start → Should show user menu
/send /menu → Should show status + credits
/send /balance → Should show balance
/send /plans → Should show available plans
/send /history → Should show recent validations
/send /help → Should show instructions
/send /quota → Should show rate limit status
/send /validate → Should start card validation flow
```

### 4. Test Card Validation (Stripe Elements)
```
1. Send /validate
2. Enter card: 4242424242424242|12|2027|123
3. Select "Stripe" mode
4. Should show:
   ✅ Card Validated Successfully
   💳 Brand: Visa
   🏦 Type: Debit
   🌍 Origin: United States
   🔒 CVC Check: ✅ Passed
   📅 Expires: 12/2027
```

### 5. Test Export Functionality
```
1. Send /history
2. Click "📤 Export Full History"
3. Choose format (JSON/CSV/TXT)
4. Should receive file with full card details
```

### 6. Check Logs
```bash
# Systemd
sudo journalctl -u card-validator-bot -f

# Docker
docker compose logs -f bot

# Railway/Render
Dashboard → Deployments → View Logs
```

---

## Monitoring & Maintenance

### Daily
- [ ] Check bot uptime (`/ping`)
- [ ] Check for errors in logs
- [ ] Monitor user activity

### Weekly
- [ ] Check database size (Supabase dashboard)
- [ ] Create backup: Admin → 💾 Backups → Create Backup
- [ ] Review audit log: Admin → 📋 Audit

### Monthly
- [ ] Export user data (Admin → 💾 Backups → Export)
- [ ] Clean old exports (`exports/` folder)
- [ ] Review admin actions
- [ ] Check rate limit patterns

---

## Troubleshooting

### Bot Doesn't Respond

**Possible Causes:**
1. Network issue (check logs)
2. Bot token incorrect
3. Not deployed properly

**Fix:**
```bash
# Check logs
sudo journalctl -u card-validator-bot -f
# OR docker compose logs -f bot

# Restart
sudo systemctl restart card-validator-bot
# OR docker compose down && docker compose up -d
```

### Stripe Elements Timeout

**Cause:** Playwright can't connect to Flask webapp

**Fix:**
1. Check webapp is running: `curl http://127.0.0.1:5000`
2. Verify `WEBAPP_URL` in `.env` matches actual port
3. Check firewall allows internal port 5000

### "Invalid API Key" in Validation

**Cause:** `STRIPE_PUBLISHABLE_KEY` is incorrect or placeholder

**Fix:**
1. Get actual key from https://dashboard.stripe.com/apikeys
2. Update `.env`: `STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_ACTUAL_KEY`
3. Restart bot

### "No active Stripe account" Error

**Cause:** Secret key not added to database

**Fix:**
1. Send `/admin` → 🔑 Stripe → Add Account
2. Enter your `sk_live_...` key
3. Click Activate

### Admin Panel Shows "Admin Only" Error

**Cause:** Your Telegram ID is not in `admins` table

**Fix:**
```sql
-- Add yourself to admins
INSERT INTO admins (telegram_id, username, role, added_by)
VALUES (YOUR_TELEGRAM_ID, 'your_username', 'super_admin', 0)
ON CONFLICT (telegram_id) DO UPDATE SET role = 'super_admin';
```

**Find your Telegram ID:**
- Message [@userinfobot](https://t.me/userinfobot) on Telegram
- It will reply with your ID

### Database Connection Error

**Check:**
1. `SUPABASE_URL` is correct
2. `SUPABASE_SERVICE_ROLE_KEY` is correct (not anon key)
3. Supabase project is active

### Playwright Browser Fails to Launch

**Fix:**
```bash
# Reinstall Chromium
playwright install chromium

# Install system dependencies (Ubuntu/Debian)
sudo apt install -y \
  libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
  libgbm1 libasound2 libxshmfence1 libx11-xcb1
```

---

## Security Checklist

- [x] `.env` in `.gitignore` (NOT committed)
- [x] Encryption key generated securely
- [x] Supabase Row Level Security enabled (recommended)
- [x] Webhook secret set (if using webhooks)
- [x] Only service_role key used (not anon key)
- [x] Admin IDs verified in database
- [x] Stripe secret key encrypted in database
- [x] Card data stored securely with hashing
- [x] Export files auto-delete after 24 hours

---

## Backup Strategy

### Automated (Code-level)
Bot creates backups via: Admin → 💾 Backups → Create Backup

### Manual (Supabase)
1. Go to Supabase Dashboard
2. Project Settings → Database
3. Click "Create backup"
4. Download SQL dump

### Recommended Schedule
- **Automated:** Daily (via code)
- **Manual:** Weekly (via Supabase)
- **Retention:** 30 days

---

## Scaling Tips

### Current Limits
- 5 validations/hour per user
- 20 validations/day per user
- 200 validations/day per Stripe account

### To Increase Capacity
1. Add more Stripe accounts (Admin → 🔑 Stripe → Add)
2. Increase rate limits in `.env` (for trusted users)
3. Use multiple Supabase connections (if needed)

---

## Architecture Overview

```
User (Telegram)
    ↓
Bot (aiogram 3.x)
    ↓
┌─────────────────────────────────┐
│ Flask Webapp (port 5000)        │
│ - Stripe Elements page          │
│ - PaymentIntent API endpoints   │
│ - Cancel endpoint               │
└─────────────────────────────────┘
    ↓
Playwright (Headless Chromium)
    ↓
Stripe Elements (Stripe.js)
    ↓
Stripe API
    ↓
Supabase (PostgreSQL)
```

---

## Cost Estimates

### Infrastructure
- **VPS (DigitalOcean/Linode):** $6-10/month
- **Supabase:** Free tier (500MB, 50k MAU)
- **Stripe:** $0.50 per validation authorization (released)

### Total Estimated Cost
- **Small scale:** $6-15/month
- **Medium scale:** $15-30/month
- **Large scale:** $30-60/month

---

## Support & Documentation

- **README.md:** Project overview
- **ENHANCEMENT_PLAN.md:** Complete feature list
- **IMPLEMENTATION_SUMMARY.md:** Phase 1 & 2
- **PHASE3_IMPLEMENTATION.md:** Phase 3 + full summary
- **STRIPE_ELEMENTS_SETUP.md:** Stripe Elements setup guide
- **database/migrations/README.md:** Migration guide

---

**Deployment Status:** ✅ READY
**Last Updated:** 2026-04-06
**Maintained By:** Development Team
