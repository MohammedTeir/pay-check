# Telegram Card Validator Bot

A private Telegram bot that validates credit/debit cards using **Stripe Elements + PaymentIntent** (`capture_method: manual`, authorize + cancel, never capture). Users pay for subscription plans via cryptocurrency, and admins manage credits through an inline keyboard interface.

## ⚠️ Risk Warning

Stripe's terms prohibit using their system solely for "card validation" without a legitimate business purpose. Repeated manual capture + cancel patterns can be detected and lead to account bans. Use at your own risk. Keep volume low, users private, and have backup Stripe accounts ready.

## Features

- 💳 **Stripe Elements validation** — Real browser-based card validation via Playwright
- 🔐 **Secure architecture** — `capture_method: manual`, never captures funds
- 💰 **Crypto payments** — Users pay via USDT/BTC, admin manages credits
- 📊 **Multi-tenant Stripe** — Multiple Stripe accounts with admin switching
- 🛡️ **Anti-ban measures** — Rate limits, duplicate detection, cooldowns
- 📝 **Full audit logging** — All validations and admin actions logged
- 🔑 **Encrypted keys** — Stripe secret keys encrypted at rest (AES-256)
- 🌐 **100% Inline UI** — No ReplyKeyboard, everything via inline buttons
- 🔄 **Webhook mode** — Production-ready with Telegram webhooks

## Architecture

```
User → Telegram → Bot (Render/Railway) → Supabase (PostgreSQL)
                                      → Stripe API (PaymentIntent)
                                      → Playwright (headless Chromium)
                                      → OpenRouter AI (analysis)
                                      → BIN Lookup APIs
```

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Telegram Bot | aiogram 3.x (async, inline only) |
| Database | Supabase (PostgreSQL) |
| Stripe SDK | stripe-python + direct HTTP |
| Web App | Flask (Waitress WSGI server) |
| Browser Automation | Playwright (headless Chromium) |
| Encryption | cryptography (Fernet/AES-256) |
| AI Analysis | OpenRouter API |
| Deployment | Docker (Render/Railway/Fly.io) |

## Setup

### 1. Supabase Setup

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** → run the migration:
   ```
   database/migrations/001_initial_schema.sql
   ```
3. Go to **Project Settings** → **API** → copy:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`

### 2. Telegram Bot Setup

1. Open Telegram, message **@BotFather**
2. Send `/newbot`, follow instructions
3. Copy the bot token → `TELEGRAM_BOT_TOKEN`

### 3. Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output → `ENCRYPTION_KEY`

### 4. Environment Variables

Create a `.env` file (copy from `.env.example`):

```env
# Application Environment
# - development: Uses polling mode (good for local testing)
# - production: Uses webhook mode (required for production deployment)
APP_ENV=development

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# Encryption
ENCRYPTION_KEY=your_fernet_key_here

# Admin IDs (comma-separated Telegram user IDs)
ADMIN_IDS=123456789,987654321

# Crypto Addresses
CRYPTO_ADDRESS_USDT=your_usdt_trc20_address
CRYPTO_ADDRESS_BTC=your_btc_address
ADMIN_CONTACT=@your_admin_username

# Stripe Elements
STRIPE_PUBLISHABLE_KEY=pk_live_xxx
STRIPE_AMOUNT_CENTS=50

# Webapp Port
WEBAPP_PORT=5000

# Limits
RATE_LIMIT_PER_HOUR=5
RATE_LIMIT_PER_DAY=20
STRIPE_ACCOUNT_DAILY_LIMIT=200
CARD_COOLDOWN_HOURS=24
```

> **💡 Environment Modes**:
> - **Development** (`APP_ENV=development`): Uses polling mode by default. No webhook setup needed.
> - **Production** (`APP_ENV=production`): Requires webhook setup with `WEBHOOK_URL` and `WEBHOOK_SECRET`.
>
> **⚠️ Security**: Never commit real credentials to `.env.example` or git. Only placeholder values should be in the repo.

#### Development Mode

For local development, simply set `APP_ENV=development` in your `.env` file:

```env
APP_ENV=development
# No webhook configuration needed
```

The bot will automatically start in polling mode.

#### Production Mode

For production deployment, set `APP_ENV=production` and configure webhook:

```env
APP_ENV=production
WEBHOOK_URL=https://your-app.onrender.com/webhook
WEBHOOK_SECRET=your_random_secret_here
```

Example environment files are provided:
- `.env.development.example` - Template for development
- `.env.production.example` - Template for production

### 5. Stripe Elements Setup

The bot uses Playwright to automate Stripe Elements validation (real browser interaction):

1. Add a Stripe publishable key via admin panel (`/admin` → **Stripe** → **Add Account**)
2. Playwright will automatically download Chromium on first build
3. The webapp serves Stripe Elements via Flask (port 5000)

### 5. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run the bot
python bot.py
```

### 6. Docker Deployment

```bash
# Build and run
docker compose up -d

# View logs
docker compose logs -f
```

## Deployment to PaaS

### Render (Recommended)

1. Push repo to GitHub
2. Create **Web Service** on [render.com](https://render.com)
3. Connect GitHub repo
4. **Build Command**: `pip install -r requirements.txt && playwright install chromium`
5. **Start Command**: `python bot.py`
6. Add all environment variables in the **Environment** tab:
   ```
   APP_ENV=production
   WEBHOOK_URL=https://your-app.onrender.com/webhook
   WEBHOOK_SECRET=<random-string>
   ```

> **Note**: In production mode (`APP_ENV=production`), the bot **requires** webhook configuration. The webhook URL and secret must be set.

### Railway

1. Import project on [railway.app](https://railway.app)
2. Add environment variables in dashboard
3. Add post-deploy command: `playwright install chromium`
4. Deploy automatically

### Fly.io

```bash
fly launch
fly secrets set TELEGRAM_BOT_TOKEN=xxx SUPABASE_URL=xxx ...
fly deploy
```

## Bot Interface

The bot uses **inline keyboard buttons** for all navigation and actions. No ReplyKeyboard menus.

### User Menu

| Button | Action |
|---|---|
| 💳 Validate | Enter card validation mode |
| 💰 Balance | Check your credits |
| 📦 Plans | View available plans |
| 📜 History | Last 10 validations |
| ❓ Help | Usage instructions |
| 🔧 Admin | Admin panel (admins only) |

### Admin Panel

| Button | Action |
|---|---|
| 👥 Users | List all users |
| 📦 Manage Plans | Create/edit/delete plans |
| 🔑 Stripe | Manage Stripe accounts |
| 📊 Stats | System statistics |
| 📋 Audit | Recent admin actions |
| 📢 Broadcast | Message all users |
| ⚙️ Settings | View/edit bot settings |

### User Commands

| Command | Description |
|---|---|
| `/start` | Welcome message + keyboard |
| `/menu` | Account status + keyboard |
| `/validate` | Enter card input mode |
| `/balance` | Check credits + keyboard |
| `/plans` | View plans + keyboard |
| `/buy <plan>` | Purchase plan (crypto) |
| `/history` | Last 10 validations + keyboard |
| `/help` | Instructions + keyboard |

### Admin Commands

| Command | Description |
|---|---|
| `/admin` | Admin panel menu + keyboard |
| `/admin_stripe` | List Stripe accounts |
| `/admin_stripe_add <label> <key>` | Add Stripe account |
| `/admin_stripe_activate <id>` | Set active account |
| `/admin_stripe_delete <id>` | Remove account |
| `/admin_stripe_rename <id> <label>` | Rename account |
| `/admin_plans` | List all plans |
| `/admin_create_plan <name> <price> <credits>` | Create plan |
| `/admin_toggle_plan <id>` | Activate/deactivate |
| `/admin_edit_plan <id> <field> <value>` | Edit field |
| `/admin_delete_plan <id>` | Delete plan |
| `/admin_users [page]` | List users |
| `/admin_user <id>` | User details |
| `/admin_search <query>` | Search users |
| `/admin_add_credits <id> <amount>` | Add credits |
| `/admin_reset_credits <id>` | Reset to 0 |
| `/admin_set_plan <id> <plan_id>` | Assign plan |
| `/admin_user_history <id>` | Validation log |
| `/admin_credit_history <id>` | Credit history |
| `/admin_ban <id>` | Ban user |
| `/admin_unban <id>` | Unban user |
| `/admin_delete_user <id>` | Delete user |
| `/admin_stats` | System statistics |
| `/admin_audit` | Recent admin actions |
| `/admin_audit_admin <id>` | Filter by admin |
| `/admin_clear_logs <30\|90>` | Clear old logs |
| `/admin_broadcast <message>` | Message all users |
| `/admin_settings` | View settings |
| `/admin_set_usdt <addr>` | Update USDT |
| `/admin_set_btc <addr>` | Update BTC |
| `/admin_set_contact <contact>` | Update contact |

## Database Schema

Tables: `users`, `plans`, `stripe_accounts`, `validation_logs`, `card_cooldowns`, `admin_logs`

See `database/migrations/001_initial_schema.sql` for full schema.

## Anti-Ban Measures

| Measure | Implementation |
|---|---|
| Stripe Elements | Real browser validation via Playwright |
| Manual capture | `capture_method: manual`, always cancelled |
| No $0 auths | Minimum $0.50 authorization |
| Rate limiting | 5/hour, 20/day per user |
| Duplicate prevention | 24h cooldown per card (salted hash) |
| Stripe daily limit | 200/day per Stripe account |
| Random delays | 1-5 seconds between Stripe ops |
| Unique metadata | UUID4 + telegram_user_id per validation |
| Encrypted keys | Fernet AES-256 at rest |

## What This System Does NOT Do

- ❌ No charge + refund pattern
- ❌ No capturing funds
- ❌ No $0 authorizations
- ❌ No bulk/automated card testing
- ❌ No Stripe billing automation
- ❌ No card balance checking (requires bank API access)

## Security Notes

- **Never** stores full card numbers — only BIN + last4 + salted hash
- Stripe secret keys encrypted at rest with Fernet (AES-256)
- All admin actions audited in `admin_logs`
- Card data handled in memory only
- VPS firewall should allow only outgoing to Stripe + Telegram API

## Testing

```bash
pytest tests/ -v
```

## Project Structure

```
card_validator_bot/
├── bot.py                        # Entry point (aiogram Dispatcher)
├── config.py                     # Config loader
├── states.py                     # FSM states (aiogram)
├── filters.py                    # Admin filter
├── wsgi.py                       # Production WSGI entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── database/
│   ├── supabase_client.py
│   └── migrations/
│       └── 001_initial_schema.sql
├── models/
│   ├── user.py
│   ├── plan.py
│   ├── stripe_account.py
│   ├── validation_log.py
│   ├── admin_log.py
│   ├── credit_transaction.py
│   └── settings.py
├── services/
│   ├── stripe_service.py
│   ├── stripe_elements_validator.py  # Playwright automation
│   ├── crypto_service.py
│   ├── rate_limiter.py
│   ├── card_validator.py
│   └── bin_lookup.py
├── handlers/
│   ├── user_handlers.py          # User commands + inline handlers
│   └── admin_handlers.py         # Admin commands + inline handlers
├── middleware/
│   └── session_timeout.py        # Session timeout middleware
├── webapp/
│   ├── app.py                    # Flask webapp (Stripe Elements page)
│   └── templates/
│       └── validate.html         # Stripe Elements form
├── utils/
│   ├── keyboards.py              # Inline keyboard builders
│   ├── formatters.py             # MarkdownV2 escaping
│   ├── card_hash.py              # Card hashing utilities
│   └── health.py                 # /ping, /health commands
└── tests/
```

## License

Private use only. Not for distribution.
