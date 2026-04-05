# Telegram Card Validator Bot

A private Telegram bot that validates credit/debit cards using Stripe's `capture_method: manual` (authorize + cancel, never capture). Users pay for subscription plans via cryptocurrency, and admins manually manage credits.

## ⚠️ Risk Warning

Stripe's terms prohibit using their system solely for "card validation" without a legitimate business purpose. Repeated manual capture + cancel patterns can be detected and lead to account bans. Use at your own risk. Keep volume low, users private, and have backup Stripe accounts ready.

## Features

- 🔐 **Secure validation** — Stripe `capture_method: manual`, never captures funds
- 💰 **Crypto payments** — Users pay via USDT/BTC, admin manually adds credits
- 📊 **Multi-tenant Stripe** — Multiple Stripe accounts with admin switching
- 🛡️ **Anti-ban measures** — Rate limits, duplicate detection, random delays
- 📝 **Full audit logging** — All validations and admin actions logged
- 🔑 **Encrypted keys** — Stripe secret keys encrypted at rest (AES-256)

## Architecture

```
User → Telegram → Bot (PaaS) → Supabase (PostgreSQL)
                          → Stripe API (PaymentIntent)
                          → BIN Lookup (local)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Telegram Bot | aiogram 3.x (async) |
| Database | Supabase (PostgreSQL) |
| Stripe SDK | stripe-python |
| Encryption | cryptography (Fernet/AES-256) |
| Deployment | Docker (Railway/Render/Fly.io) |

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
TELEGRAM_BOT_TOKEN=your_bot_token_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
ENCRYPTION_KEY=your_fernet_key_here
ADMIN_IDS=123456789,987654321
CRYPTO_ADDRESS_USDT=your_usdt_trc20_address
CRYPTO_ADDRESS_BTC=your_btc_address
ADMIN_CONTACT=@your_admin_username
STRIPE_AMOUNT_CENTS=50
RATE_LIMIT_PER_HOUR=5
RATE_LIMIT_PER_DAY=20
STRIPE_ACCOUNT_DAILY_LIMIT=200
CARD_COOLDOWN_HOURS=24
```

### 5. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

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

### Railway

1. Push repo to GitHub
2. Import project on [railway.app](https://railway.app)
3. Add environment variables in Railway dashboard
4. Deploy automatically

### Render

1. Create **Web Service** on [render.com](https://render.com)
2. Connect GitHub repo
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python bot.py`
5. Add environment variables

### Fly.io

```bash
fly launch
fly secrets set TELEGRAM_BOT_TOKEN=xxx SUPABASE_URL=xxx ...
fly deploy
```

## Bot Interface

The bot uses **persistent ReplyKeyboard menus** at the bottom of the chat for easy navigation, plus direct commands.

### User Menu Buttons

| Button | Action |
|---|---|
| 💳 Validate | Enter card validation mode |
| 💰 Balance | Check your credits |
| 📦 Plans | View available plans |
| 📜 History | Last 10 validations |
| ❓ Help | Usage instructions |
| 🔧 Admin | Admin panel (admins only) |

### Admin Menu Buttons

| Button | Action |
|---|---|
| 👥 Users | List all users |
| 📦 Manage Plans | Create/edit/delete plans |
| 🔑 Stripe | Manage Stripe accounts |
| 📊 Stats | System statistics |
| 📋 Audit | Recent admin actions |
| 📢 Broadcast | Message all users |
| ⚙️ Settings | View/edit bot settings |
| 🔙 Close Menu | Return to user keyboard |

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
| Manual capture | `capture_method: manual`, always cancelled |
| No $0 auths | Minimum $0.50 authorization |
| Rate limiting | 5/hour, 20/day per user |
| Duplicate prevention | 24h cooldown per card (salted hash) |
| Stripe daily limit | 200/Day per Stripe account |
| Random delays | 1-5 seconds between Stripe ops |
| Unique metadata | UUID4 + telegram_user_id per validation |
| Encrypted keys | Fernet AES-256 at rest |

## What This System Does NOT Do

- ❌ No public web interface
- ❌ No charge + refund pattern
- ❌ No capturing funds
- ❌ No $0 authorizations
- ❌ No bulk/automated card testing
- ❌ No Stripe billing automation

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
│   ├── crypto_service.py
│   ├── rate_limiter.py
│   ├── card_validator.py
│   └── bin_lookup.py
├── handlers/
│   ├── user_handlers.py          # User commands + button handlers
│   └── admin_handlers.py         # Admin commands + button handlers
├── utils/
│   ├── keyboards.py              # ReplyKeyboard + InlineKeyboard builders
│   ├── formatters.py             # MarkdownV2 escaping
│   └── card_hash.py              # Card hashing utilities
└── tests/
```

## License

Private use only. Not for distribution.
