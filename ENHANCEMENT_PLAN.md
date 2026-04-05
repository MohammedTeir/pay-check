# Enhancement Plan - Card Validator Bot

**Generated:** 2026-04-05  
**Project:** Telegram Card Validator Bot  
**Status:** Pending Review

---

## Table of Contents

1. [Well-Implemented Features](#well-implemented-features)
2. [High Priority Enhancements](#high-priority-enhancements)
3. [Medium Priority Enhancements](#medium-priority-enhancements)
4. [Low Priority Enhancements](#low-priority-enhancements)
5. [Quick Wins](#quick-wins)
6. [Potential Issues](#potential-issues)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Well-Implemented Features

The following features are **solid and require no enhancement**:

### Architecture & Structure
- ✅ Clean separation of concerns (handlers, services, models, utils, database)
- ✅ aiogram 3.x async framework properly implemented
- ✅ FSM state management for user flows
- ✅ Modular service layer (stripe_service, card_validator, rate_limiter, bin_lookup, ai_validation)

### Security
- ✅ AES-256 Fernet encryption for Stripe secret keys at rest
- ✅ Salted card hashing to prevent duplicate validations
- ✅ Rate limiting (5/hour, 20/day per user)
- ✅ Card cooldown periods (24h)
- ✅ Admin audit logging for all administrative actions

### Admin System
- ✅ Full-featured admin panel with inline keyboards
- ✅ User management (add credits, ban, search, view history)
- ✅ Stripe account management (add, activate, rename, delete)
- ✅ Plan management (create, edit, toggle, delete)
- ✅ Broadcast messaging to all users
- ✅ Admin settings management

### Database & Infrastructure
- ✅ Complete Supabase integration with proper schema
- ✅ Multi-tenant Stripe account support
- ✅ Docker and docker-compose for deployment
- ✅ Comprehensive database models (users, plans, stripe_accounts, validation_logs, admin_logs, credit_transactions)

### Testing
- ✅ Unit tests for core services (card_validator, crypto_service, rate_limiter)

---

## High Priority Enhancements

These enhancements address **critical gaps** that could cause data loss, security issues, or operational failures.

### 1. Error Recovery & Retry Logic

**Problem:** Network failures during Stripe validation could leave operations in an inconsistent state. If a PaymentIntent is created but the bot crashes before cancellation, funds could be captured.

**Implementation:**
```
services/retry_handler.py
- Exponential backoff retry decorator (3 attempts)
- Idempotency keys for Stripe operations
- Transaction rollback for database operations
- Dead letter queue for failed operations
- Alert admin when retry limit exceeded
```

**Files to create:**
- `services/retry_handler.py` - Retry logic with exponential backoff
- `services/transaction_manager.py` - Database transaction management

**Files to modify:**
- `services/stripe_service.py` - Add retry decorators
- `services/card_validator.py` - Add transaction safety

**Estimated complexity:** Medium

---

### 2. Webhook Mode Support

**Problem:** Currently uses polling-only mode. Webhooks are more efficient, reliable, and recommended for production deployments on PaaS platforms.

**Implementation:**
```
config.py
- Add WEBHOOK_URL, WEBHOOK_SECRET, USE_WEBHOOK env vars
- Validate webhook URL format

bot.py
- Add webhook setup on startup
- Add webhook route handler
- Add graceful fallback to polling if webhook fails

Dockerfile/docker-compose.yml
- Expose port 8080 for webhook endpoint
- Add health check endpoint
```

**Files to create:**
- `webhook_handler.py` - Webhook endpoint handler

**Files to modify:**
- `config.py` - Add webhook configuration
- `bot.py` - Add webhook setup and routing
- `Dockerfile` - Expose webhook port
- `docker-compose.yml` - Add port mapping

**Estimated complexity:** Medium

---

### 3. Health Check Endpoint

**Problem:** No way to monitor bot status externally. PaaS platforms need health checks to detect crashes and auto-restart.

**Implementation:**
```
bot.py
- Add /health command that checks:
  - Database connectivity (Supabase ping)
  - Stripe API availability
  - Bot token validity
  - Response time metrics
  - Uptime duration

utils/health.py
- Health check service
- Status cache (last check timestamp)
- Metrics collection

Endpoint: GET https://bot-url/health (for webhooks)
Command: /health (for admins)
```

**Files to create:**
- `utils/health.py` - Health check service

**Files to modify:**
- `bot.py` - Add health endpoint
- `handlers/admin_handlers.py` - Add /health command for admins

**Estimated complexity:** Low

---

### 4. Backup & Export System

**Problem:** No automated database backups. If Supabase project is deleted or corrupted, all user data, credits, and logs are lost.

**Implementation:**
```
services/backup_service.py
- Automated daily backups via Supabase API
- Export to JSON/CSV format
- Store encrypted backups locally or in cloud storage
- Rotation policy (keep last 30 days)

commands:
- /admin_backup_now - Trigger immediate backup
- /admin_backup_list - List available backups
- /admin_backup_export <table> - Export specific table
- /admin_backup_restore <backup_id> - Restore backup (dangerous)
```

**Files to create:**
- `services/backup_service.py` - Backup and restore logic
- `handlers/backup_handlers.py` - Backup command handlers

**Files to modify:**
- `bot.py` - Register backup handlers
- `states.py` - Add backup-related FSM states
- `utils/keyboards.py` - Add backup buttons to admin panel

**Estimated complexity:** Medium

---

### 5. User Notifications

**Problem:** Users receive no proactive alerts. They might not know their balance is low, plan expired, or validation failed due to rate limits.

**Implementation:**
```
services/notification_service.py
- Queue-based notification system
- Scheduled checks for:
  - Low balance (< 10 credits)
  - Plan expiry (7 days before, 1 day before)
  - Rate limit warnings (80% reached)
  - System announcements from admin
  - Validation batch completion

notifications:
- Balance alerts (daily check when < 10 credits)
- Plan renewal reminders
- Rate limit warnings
- Broadcast delivery confirmations
```

**Files to create:**
- `services/notification_service.py` - Notification queue and delivery
- `models/notification.py` - Notification model

**Files to modify:**
- `services/card_validator.py` - Trigger validation notifications
- `database/supabase_client.py` - Add notifications table
- `handlers/user_handlers.py` - Add notification preferences

**Estimated complexity:** Medium

---

## Medium Priority Enhancements

These enhancements improve **user experience, admin control, and operational efficiency**.

### 6. Multi-Language Support (i18n)

**Problem:** Bot is English-only, limiting potential user base in non-English speaking regions.

**Implementation:**
```
locales/
  en.json
  es.json
  ru.json
  zh.json
  ar.json

utils/i18n.py
- Language detection from Telegram profile
- Translation loader
- Fallback to English for missing strings
- Admin command to change user language

Commands:
- /language - Change language
- /admin_set_language <id> <lang> - Set user language
```

**Files to create:**
- `utils/i18n.py` - Internationalization service
- `locales/` - Translation files (JSON format)

**Files to modify:**
- All handler files - Replace hardcoded strings with i18n calls
- `utils/formatters.py` - Add language-aware formatting
- `utils/keyboards.py` - Localize keyboard buttons

**Estimated complexity:** High (but high impact)

---

### 7. Cryptocurrency Payment Verification

**Problem:** Crypto payments rely entirely on manual admin confirmation. This creates delays, potential for human error, and requires admin to be online 24/7.

**Implementation:**
```
services/crypto_payment_service.py
- Integrate with blockchain explorers:
  - USDT TRC20: tronscan.org API
  - BTC: blockchain.info API
- Monitor wallet addresses for incoming transactions
- Auto-confirm payments when amount matches
- Generate unique deposit amounts or memos for tracking
- Auto-add credits upon confirmation

commands:
- /admin_toggle_auto_verify - Enable/disable auto-verification
- /admin_payment_status - Check monitoring status
```

**Files to create:**
- `services/crypto_payment_service.py` - Blockchain monitoring
- `models/payment.py` - Payment tracking model

**Files to modify:**
- `services/crypto_service.py` - Add verification logic
- `handlers/admin_handlers.py` - Add auto-verify controls
- `database/supabase_client.py` - Add payments table

**Estimated complexity:** High

---

### 8. Analytics Dashboard

**Problem:** Only text-based statistics available. Admins can't visualize trends, peak usage times, or revenue metrics.

**Implementation:**
```
services/analytics_service.py
- Metrics collection:
  - Validations per hour/day/week
  - Revenue tracking (credits purchased)
  - User growth rate
  - Most active users
  - BIN/country distribution
  - Stripe account usage distribution

Export formats:
- Text summary (current)
- Inline keyboard with charts (generate PNG images)
- CSV export for spreadsheet analysis

commands:
- /admin_analytics - View analytics menu
- /admin_analytics_chart <type> <period> - Generate chart
- /admin_analytics_export <format> - Download data
```

**Files to create:**
- `services/analytics_service.py` - Analytics engine
- `utils/chart_generator.py` - Chart image generation (matplotlib)

**Files to modify:**
- `handlers/admin_handlers.py` - Add analytics commands
- `utils/keyboards.py` - Add analytics buttons

**Estimated complexity:** Medium

---

### 9. Enhanced Card Type Detection

**Problem:** Current BIN lookup provides basic info. Could leverage AI (OpenRouter already configured) for enhanced card metadata enrichment.

**Implementation:**
```
services/ai_card_enrichment.py
- Use OpenRouter AI to:
  - Validate BIN format and provide detailed bank info
  - Identify card subtype (prepaid, debit, credit, corporate)
  - Provide issuing bank contact info
  - Estimate card validation success rate by BIN
  - Flag high-risk BINs (known fraud patterns)

commands:
- /bin <6-8 digits> - Quick BIN lookup
- /admin_bin_stats - BIN usage statistics
```

**Files to create:**
- `services/ai_card_enrichment.py` - AI-powered BIN analysis

**Files to modify:**
- `services/bin_lookup.py` - Integrate AI enrichment
- `services/card_validator.py` - Add enriched validation results
- `handlers/user_handlers.py` - Show enhanced card info

**Estimated complexity:** Medium

---

### 10. Refund & Credit Reversal System

**Problem:** No way to reverse accidental credit additions. If admin makes a mistake, there's no audit trail or correction mechanism.

**Implementation:**
```
commands:
- /admin_reverse_credit <tx_id> - Reverse specific transaction
- /admin_adjust_credits <id> <amount> - Negative amount = deduct

Database:
- Add credit_transactions.reversible (boolean)
- Add credit_transactions.reversed_by (admin_id)
- Add reversal audit log

Safety:
- Require confirmation before reversal
- Log all reversals in admin_logs
- Notify user of credit adjustment
- Prevent reversal of already-reversed transactions
```

**Files to create:**
- (No new files - extends existing credit_transaction model)

**Files to modify:**
- `models/credit_transaction.py` - Add reversal fields
- `handlers/admin_handlers.py` - Add reversal commands
- `services/crypto_service.py` - Add reversal logic
- `database/migrations/` - Add reversal schema migration

**Estimated complexity:** Low

---

### 11. Session Timeout for FSM States

**Problem:** FSM states persist indefinitely in MemoryStorage. If user starts card validation then abandons it, the bot remains in that state until timeout or restart.

**Implementation:**
```
services/session_manager.py
- Track last activity timestamp per user
- Auto-reset FSM state after inactivity (15 minutes default)
- Notify user when session expires
- Configurable timeout per state type

config.py:
- SESSION_TIMEOUT_MINUTES = 15
- VALIDATION_TIMEOUT_MINUTES = 5

bot.py:
- Add middleware to check session expiry
- Auto-logout and notify user
```

**Files to create:**
- `services/session_manager.py` - Session timeout logic
- `middleware/session_timeout.py` - aiogram middleware

**Files to modify:**
- `bot.py` - Add session middleware
- `config.py` - Add session timeout config

**Estimated complexity:** Low

---

## Low Priority Enhancements

These are **nice-to-have features** that improve polish and long-term maintainability.

### 12. Redis Cache Layer

**Problem:** MemoryStorage is lost on bot restart. Redis provides persistent caching and enables horizontal scaling.

**Implementation:**
```
- Replace MemoryStorage with RedisStorage
- Cache BIN lookup results (TTL: 24h)
- Cache rate limit counters
- Store session state persistently
- Enable multi-instance deployment

docker-compose.yml:
- Add Redis service
- Update bot service to depend on Redis
```

**Files to create:**
- `services/cache_service.py` - Redis wrapper

**Files to modify:**
- `bot.py` - Use RedisStorage
- `services/rate_limiter.py` - Use Redis for counters
- `services/bin_lookup.py` - Cache results in Redis
- `docker-compose.yml` - Add Redis container
- `requirements.txt` - Add aioredis

**Estimated complexity:** Medium

---

### 13. Prometheus Metrics & Monitoring

**Problem:** No real-time monitoring of bot performance, validation success rates, or system health.

**Implementation:**
```
services/metrics_service.py
- Expose Prometheus metrics:
  - bot_validations_total (counter)
  - bot_validation_errors_total (counter)
  - bot_validation_duration_seconds (histogram)
  - bot_active_users (gauge)
  - bot_stripe_api_calls_total (counter)
  - bot_database_query_duration_seconds (histogram)

Endpoint: GET /metrics (for Prometheus scraper)

Grafana dashboard templates included
```

**Files to create:**
- `services/metrics_service.py` - Prometheus integration
- `monitoring/grafana_dashboard.json` - Dashboard config

**Files to modify:**
- `bot.py` - Add /metrics endpoint
- All service files - Add metric collection points

**Estimated complexity:** Medium

---

### 14. Admin Role Hierarchy

**Problem:** All admins have equal powers. No way to create "support" admins who can only add credits, vs "super" admins who can delete users.

**Implementation:**
```
Database:
- Add admin_roles table with permissions
- Roles: super_admin, moderator, support, viewer

Permissions:
- super_admin: Full access
- moderator: User management + credits
- support: View users + add credits only
- viewer: Read-only access

commands:
- /admin_set_role <admin_id> <role>
- /admin_list_roles
```

**Files to create:**
- `models/admin_role.py` - Role model
- `middleware/admin_permissions.py` - Permission checker

**Files to modify:**
- `database/migrations/` - Add roles schema
- `filters.py` - Add role-based filtering
- `handlers/admin_handlers.py` - Restrict by role

**Estimated complexity:** Medium

---

### 15. Card Validation History Export

**Problem:** Users can't download or export their validation history. Only view last 10 in bot.

**Implementation:**
```
commands:
- /export_history <format> - Download validation log
- Formats: CSV, JSON, TXT

services/export_service.py
- Generate formatted files
- Send as Telegram document
- Auto-delete file after 24h (privacy)
- Include summary statistics
```

**Files to create:**
- `services/export_service.py` - Export logic

**Files to modify:**
- `handlers/user_handlers.py` - Add export command
- `utils/keyboards.py` - Add export button

**Estimated complexity:** Low

---

### 16. Automated Testing CI/CD

**Problem:** No automated testing pipeline. Code quality depends on manual testing.

**Implementation:**
```
.github/workflows/ci.yml
- Run tests on every push
- Lint check (flake8, black, isort)
- Type checking (mypy)
- Build Docker image
- Upload coverage report

tests/
- Add integration tests
- Add handler tests
- Add database mock tests
- Increase coverage to >80%
```

**Files to create:**
- `.github/workflows/ci.yml` - GitHub Actions workflow
- `tests/test_handlers.py` - Handler tests
- `tests/test_integration.py` - Integration tests
- `.coveragerc` - Coverage config

**Files to modify:**
- `requirements.txt` - Add flake8, black, mypy, coverage

**Estimated complexity:** Medium

---

### 17. API Rate Limit Feedback

**Problem:** Users have no visibility into their remaining quota. They only discover limits when blocked.

**Implementation:**
```
After each validation:
- Show remaining hourly/daily quota
- Show cooldown status
- Show Stripe account capacity

Commands:
- /quota - View current rate limit status
- /quota_reset - Show when limits reset

utils/formatters.py:
- Add rate limit progress bar
- Add time-to-reset countdown
```

**Files to create:**
- (No new files)

**Files to modify:**
- `services/card_validator.py` - Return quota info
- `handlers/user_handlers.py` - Add /quota command
- `utils/formatters.py` - Add progress bar formatting
- `utils/keyboards.py` - Add quota button to menu

**Estimated complexity:** Low

---

## Potential Issues

These are **existing problems** that should be addressed immediately.

### Issue 1: `.env` File Contains Real Credentials ⚠️ CRITICAL

**Risk:** Credentials are committed to version control. Anyone with repo access can:
- Access your Supabase database
- Use your Stripe accounts
- Control your Telegram bot
- Access your crypto wallets

**Action Required:**
```bash
# 1. Add to .gitignore immediately
echo ".env" >> .gitignore

# 2. Remove from git history
git rm --cached .env
git commit -m "Remove .env from version control"

# 3. Rotate ALL credentials immediately
# - Generate new Supabase service_role key
# - Regenerate Telegram bot token via @BotFather
# - Generate new ENCRYPTION_KEY and re-encrypt Stripe keys
# - Move crypto addresses to database-only storage
```

---

### Issue 2: No Graceful Shutdown

**Risk:** Bot doesn't cleanly stop polling. On PaaS restart, this could cause:
- Duplicate webhook registrations
- Lost FSM states
- Incomplete Stripe operations
- Database connection leaks

**Action Required:**
```python
# bot.py - Add signal handler
import signal

async def graceful_shutdown():
    logger.info("Shutting down gracefully...")
    await dp.storage.close()
    await bot.session.close()

for sig in (signal.SIGTERM, signal.SIGINT):
    asyncio.get_event_loop().add_signal_handler(sig, graceful_shutdown)
```

---

### Issue 3: MemoryStorage Lost on Restart

**Risk:** All FSM states are lost when bot restarts. Users mid-validation will get confused responses.

**Action Required:**
- Short-term: Add recovery message ("Please start over")
- Long-term: Migrate to RedisStorage or DatabaseStorage

---

### Issue 4: No Input Sanitization

**Risk:** Admin text inputs (add credits, create plans, etc.) aren't validated for:
- SQL injection (mitigated by Supabase ORM, but still)
- Negative numbers where not expected
- Invalid formats (email, username, crypto address)
- Buffer overflow (very long strings)

**Action Required:**
```python
# Add validation to all admin inputs
def validate_positive_integer(value):
    if not value.isdigit() or int(value) <= 0:
        raise ValueError("Must be a positive number")
    return int(value)

def validate_crypto_address(address, currency):
    # Regex validation for BTC/USDT addresses
    patterns = {
        'BTC': r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}$',
        'USDT_TRC20': r'^T[a-zA-HJ-NP-Z0-9]{33}$'
    }
    if not re.match(patterns[currency], address):
        raise ValueError(f"Invalid {currency} address")
```

---

### Issue 5: Log File Grows Indefinitely

**Risk:** `logs/bot.log` will eventually fill disk space on PaaS, causing crash.

**Action Required:**
```python
# bot.py - Add rotating file handler
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler(
    'logs/bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

---

## Quick Wins (< 1 hour each)

These can be implemented **immediately** with minimal effort:

### ✅ 1. Add `.env` to `.gitignore`
```
.env
*.env.bak
```

### ✅ 2. Add Log Rotation
```python
from logging.handlers import RotatingFileHandler
# Replace FileHandler with RotatingFileHandler (see Issue 5)
```

### ✅ 3. Add Graceful Shutdown Handler
```python
import signal
# Add signal handlers for SIGTERM/SIGINT (see Issue 2)
```

### ✅ 4. Add `/ping` Health Command
```python
@dp.message.register(Command("ping"))
async def cmd_ping(message: Message):
    await message.answer("🟢 Bot is running!")
```

### ✅ 5. Validate Admin Text Inputs
```python
# Add input validation to all admin handlers
# Check Issue 4 for examples
```

### ✅ 6. Add User-Friendly Error Messages
```python
# Replace generic "Error occurred" with specific messages:
# - "Stripe is temporarily unavailable, please try again in 5 minutes"
# - "Your card is on cooldown (try again in X hours)"
# - "Rate limit reached (X/Y per hour)"
```

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
**Priority:** Security and stability

- [ ] Issue 1: Remove `.env` from git, rotate credentials
- [ ] Issue 2: Add graceful shutdown
- [ ] Issue 5: Add log rotation
- [ ] Quick Win 4: Add `/ping` command
- [ ] Quick Win 5: Add input validation

### Phase 2: Reliability (Week 2)
**Priority:** Prevent data loss

- [ ] High Priority 1: Error recovery & retry logic
- [ ] High Priority 3: Health check endpoint
- [ ] High Priority 5: User notifications
- [ ] Medium Priority 10: Refund & credit reversal
- [ ] Medium Priority 11: Session timeout

### Phase 3: Production Readiness (Week 3)
**Priority:** Deploy to production safely

- [ ] High Priority 2: Webhook mode support
- [ ] High Priority 4: Backup & export system
- [ ] Medium Priority 7: Crypto payment verification
- [ ] Low Priority 15: Validation history export
- [ ] Low Priority 17: API rate limit feedback

### Phase 4: Enhancement (Week 4)
**Priority:** Improve user/admin experience

- [ ] Medium Priority 6: Multi-language support
- [ ] Medium Priority 8: Analytics dashboard
- [ ] Medium Priority 9: Enhanced card detection
- [ ] Low Priority 12: Redis cache layer
- [ ] Low Priority 13: Prometheus metrics

### Phase 5: Long-term (Month 2+)
**Priority:** Scale and maintain

- [ ] Medium Priority 14: Admin role hierarchy
- [ ] Low Priority 16: Automated testing CI/CD
- [ ] Documentation updates
- [ ] Performance optimization
- [ ] Security audit

---

## Estimated Effort Summary

| Phase | Duration | Complexity | Risk Level |
|-------|----------|------------|------------|
| Phase 1: Critical Fixes | 1 week | Low | High (if not done) |
| Phase 2: Reliability | 1 week | Medium | Medium |
| Phase 3: Production | 1 week | Medium-High | Medium |
| Phase 4: Enhancement | 1 week | Medium-High | Low |
| Phase 5: Long-term | 1+ month | High | Low |

**Total Estimated Effort:** 4-6 weeks for full implementation

---

## Cost Considerations

### New Infrastructure Requirements

| Service | Purpose | Estimated Cost |
|---------|---------|----------------|
| Redis (optional) | Cache layer | Free (self-hosted) / $5-15/mo (managed) |
| Blockchain APIs | Payment verification | Free tier available |
| OpenRouter AI | Enhanced BIN lookup | Pay-per-use (~$0.01/query) |
| Grafana Cloud | Metrics dashboard | Free tier (10k metrics) |
| Additional PaaS resources | Webhook port, metrics | Minimal (<$5/mo) |

**Total Additional Cost:** $0-25/mo depending on features enabled

---

## Risk Assessment

| Enhancement | Risk | Mitigation |
|-------------|------|------------|
| Webhook Mode | Medium | Fallback to polling |
| Auto Payment Verify | Medium | Manual override available |
| AI Card Enrichment | Low | Fallback to basic BIN lookup |
| Redis Cache | Low | Graceful degradation |
| Admin Role Hierarchy | Low | Super admin always exists |
| Crypto Integration | High | Start with manual verification |

---

## Success Metrics

After implementation, track:

- **Bot Uptime:** Target 99.9% (health checks)
- **Validation Success Rate:** Target >95%
- **Admin Response Time:** Target <5 min (notifications)
- **User Retention:** Target >80% monthly
- **Error Rate:** Target <1% of validations
- **Support Tickets:** Target 50% reduction (better UX)

---

## Appendix: File Changes Summary

### New Files to Create (18 files)
```
services/retry_handler.py
services/transaction_manager.py
services/backup_service.py
services/notification_service.py
services/crypto_payment_service.py
services/analytics_service.py
services/ai_card_enrichment.py
services/session_manager.py
services/cache_service.py
services/metrics_service.py
services/export_service.py
utils/health.py
utils/i18n.py
utils/chart_generator.py
middleware/session_timeout.py
middleware/admin_permissions.py
models/notification.py
models/payment.py
models/admin_role.py
```

### Files to Modify (14 files)
```
config.py
bot.py
Dockerfile
docker-compose.yml
requirements.txt
handlers/user_handlers.py
handlers/admin_handlers.py
services/stripe_service.py
services/card_validator.py
services/bin_lookup.py
services/crypto_service.py
services/rate_limiter.py
utils/formatters.py
utils/keyboards.py
database/supabase_client.py
```

### Database Migrations (5 migrations)
```
database/migrations/002_add_notifications.sql
database/migrations/003_add_payments.sql
database/migrations/004_add_admin_roles.sql
database/migrations/005_add_credit_reversals.sql
database/migrations/006_add_user_preferences.sql
```

---

## Notes

- All enhancements are **optional** - prioritize based on your needs
- Phases can be adjusted or skipped as needed
- Existing functionality will not be broken by these changes
- Backwards compatibility maintained throughout
- Test thoroughly in development before deploying to production

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-05  
**Maintained By:** Development Team
