# Deployment Guide - Card Validator Bot

**Date:** 2026-04-05  
**Status:** Ready for Production ✅

---

## Pre-Deployment Checklist

### ✅ Code is Ready
- [x] All enhancements implemented (Phases 1-3)
- [x] Admin checks purely database-driven
- [x] Input validation added
- [x] Error handling & retry logic
- [x] Graceful shutdown
- [x] Log rotation
- [x] Session timeout middleware

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

### 6. Credit Reversals (NEW - from enhancements)
```
database/migrations/002_add_credit_reversals.sql
```

### 7. Backups Table (NEW - from enhancements)
```
database/migrations/003_add_backups_table.sql
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

## Deployment Options

### Option 1: Railway (Recommended - Easiest)

**Step 1:** Push to GitHub
```bash
# Check .env is NOT tracked
git status | grep ".env"  # Should not appear

# Add and commit
git add .
git commit -m "Production ready deployment"

# Push
git push origin main
```

**Step 2:** Deploy on Railway
1. Go to [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub"
3. Select your repository
4. Railway auto-detects Python app

**Step 3:** Add Environment Variables
In Railway dashboard, add these variables:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `SUPABASE_URL` | `https://your-project.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Your service role key |
| `ENCRYPTION_KEY` | Fernet key (generate with Python) |
| `ADMIN_IDS` | `123456789,987654321` (comma-separated) |
| `CRYPTO_ADDRESS_USDT` | Your USDT TRC20 address |
| `CRYPTO_ADDRESS_BTC` | Your BTC address |
| `ADMIN_CONTACT` | `@your_admin_username` |
| `STRIPE_AMOUNT_CENTS` | `50` |
| `RATE_LIMIT_PER_HOUR` | `5` |
| `RATE_LIMIT_PER_DAY` | `20` |
| `STRIPE_ACCOUNT_DAILY_LIMIT` | `200` |
| `CARD_COOLDOWN_HOURS` | `24` |

**Step 4:** Deploy
Railway auto-deploys. Check logs:
```
Railway Dashboard → Deployments → View Logs
```

---

### Option 2: Render

**Step 1:** Create Web Service
1. Go to [render.com](https://render.com)
2. New → Web Service
3. Connect GitHub repo

**Step 2:** Configuration
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python bot.py`
- **Environment:** Python 3

**Step 3:** Add Environment Variables
Same as Railway (see table above)

**Step 4:** Deploy
Render auto-deploys. Bot runs on port 8080 (if webhook enabled).

---

### Option 3: Fly.io

**Step 1:** Install Fly CLI
```bash
# Windows (via winget)
winget install Fly.Flyctl

# Or
curl -L https://fly.io/install.sh | sh
```

**Step 2:** Login & Launch
```bash
fly auth login
fly launch
```

**Step 3:** Set Secrets
```bash
fly secrets set TELEGRAM_BOT_TOKEN=xxx
fly secrets set SUPABASE_URL=https://your-project.supabase.co
fly secrets set SUPABASE_SERVICE_ROLE_KEY=xxx
fly secrets set ENCRYPTION_KEY=xxx
fly secrets set ADMIN_IDS=1151779389
fly secrets set CRYPTO_ADDRESS_USDT=xxx
fly secrets set CRYPTO_ADDRESS_BTC=xxx
fly secrets set ADMIN_CONTACT=@your_username
```

**Step 4:** Deploy
```bash
fly deploy
```

---

### Option 4: Docker (Any VPS)

**Step 1:** Setup VPS
```bash
# SSH into VPS
ssh root@your-vps-ip

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**Step 2:** Clone & Configure
```bash
# Clone repo
git clone https://github.com/your-username/card_validator_bot.git
cd card_validator_bot

# Create .env file
nano .env
# Add all environment variables (see below)
```

**Step 3:** Deploy
```bash
# Build and run
docker compose up -d --build

# View logs
docker compose logs -f bot

# Stop
docker compose down
```

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

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIPE_AMOUNT_CENTS` | `50` | Authorization amount ($0.50) |
| `RATE_LIMIT_PER_HOUR` | `5` | Validations per hour |
| `RATE_LIMIT_PER_DAY` | `20` | Validations per day |
| `STRIPE_ACCOUNT_DAILY_LIMIT` | `200` | Stripe daily limit |
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

### 3. Test User Features
```
Send /start → Should show user menu
Send /menu → Should show status + credits
Send /balance → Should show balance
Send /plans → Should show available plans
Send /history → Should show recent validations
Send /help → Should show instructions
```

### 4. Test Admin Features
```
Click 🔧 Admin Panel → Should open admin menu
Click 👥 Users → Should list users
Click 🔑 Stripe → Should list Stripe accounts
Click 📦 Plans → Should list plans
Click 📊 Stats → Should show system statistics
Click 📋 Audit → Should show admin actions
Click 📢 Broadcast → Should allow broadcast
Click 💾 Backups → Should show backup menu
Click ⚙️ Settings → Should show settings
```

### 5. Test Validation
```
Send card: 4242424242424242|12|2027|123
Should parse and ask for validation mode
Should show cost as "free" if admin
Should NOT deduct credits if admin
```

### 6. Check Logs
```
# Railway
Dashboard → Deployments → View Logs

# Render
Dashboard → Logs

# Docker
docker compose logs -f bot

# Fly.io
fly logs
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
docker compose logs bot
# OR Railway/Render dashboard

# Restart
docker compose down && docker compose up -d
# OR Railway: Settings → Restart
```

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

### Credits Not Deducting for Normal Users

**Cause:** `_is_admin()` returning True incorrectly

**Fix:**
```sql
-- Check if user is accidentally in admins table
SELECT telegram_id, username, role FROM admins;

-- Remove if needed
DELETE FROM admins WHERE telegram_id = 123456789;
```

### Database Connection Error

**Check:**
1. `SUPABASE_URL` is correct
2. `SUPABASE_SERVICE_ROLE_KEY` is correct (not anon key)
3. Supabase project is active

### Stripe Errors

**Check:**
1. Stripe account is active: Admin → 🔑 Stripe
2. Secret key format: starts with `sk_live_` or `sk_test_`
3. Stripe account is not banned

---

## Security Checklist

- [x] `.env` in `.gitignore` (NOT committed)
- [x] Encryption key generated securely
- [x] Supabase Row Level Security enabled (recommended)
- [x] Webhook secret set (if using webhooks)
- [x] Only service_role key used (not anon key)
- [x] Admin IDs verified in database
- [x] Stripe keys encrypted at rest

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

## Cost Estimates

### Free Tier (Railway/Render)
- **Railway:** $5/month free credit
- **Render:** Free tier available (sleeps after 15min)
- **Fly.io:** 3 free VMs (shared-cpu)

### Supabase
- **Free tier:** 500MB database, 50,000 monthly active users
- **Pro tier:** $25/month (if you exceed free tier)

### Total Estimated Cost
- **Small scale:** $0-5/month
- **Medium scale:** $10-25/month
- **Large scale:** $25-50/month

---

## Support & Documentation

- **README.md:** Project overview
- **ENHANCEMENT_PLAN.md:** Complete feature list
- **IMPLEMENTATION_SUMMARY.md:** Phase 1 & 2
- **PHASE3_IMPLEMENTATION.md:** Phase 3 + full summary
- **docs/WEBHOOK_SETUP.md:** Webhook configuration
- **FIXES/ADMIN_ID_FIX.md:** Admin check documentation

---

**Deployment Status:** ✅ READY  
**Last Updated:** 2026-04-05  
**Maintained By:** Development Team
