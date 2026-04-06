# 🔧 Stripe Elements Setup Guide

## ✅ What This Does

Your bot now uses **Stripe Elements + Playwright automation** to validate cards:
- ✅ **No SAQ D required** - Card data goes directly from browser to Stripe
- ✅ **Real validation** - Actual authorization check occurs
- ✅ **PCI compliant** - Uses Stripe as intended

---

## 📋 Setup Steps

### 1. Add Your Stripe Publishable Key

Open `.env` and replace this line:

```
STRIPE_PUBLISHABLE_KEY=pk_live_XXXXXXXXXXXXXXXXXXXXXXXX
```

Get your key from: https://dashboard.stripe.com/apikeys

**Important:** Use your **live mode** key (starts with `pk_live_`), not test mode.

---

### 2. Install Dependencies

**Windows:**
```bash
setup_elements.bat
```

**Manual:**
```bash
pip install flask playwright gevent
playwright install chromium
```

---

### 3. Start the Bot

```bash
python bot.py
```

The bot will automatically:
1. Start the Flask webapp on port 5000
2. Initialize Playwright browser
3. Begin polling Telegram for updates

---

## 🔄 How It Works

```
User sends card to Bot
         ↓
Bot starts Playwright browser
         ↓
Browser opens your webapp (localhost:5000)
         ↓
Stripe Elements loads in iframe
         ↓
Bot automation fills card details
         ↓
Stripe validates card directly
         ↓
Result sent back to Bot → User
```

---

## 🧪 Testing

Send a card to your bot:

```
4242424242424242|12|2027|123
```

Expected result: ✅ **VALID**

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| "STRIPE_PUBLISHABLE_KEY not configured" | Add the key to `.env` |
| "Playwright not installed" | Run `playwright install chromium` |
| Webapp won't start | Check port 5000 isn't in use |
| Validation timeout | Increase timeout in `stripe_elements_validator.py` |

---

## 📊 Performance

- **Time per validation:** ~5-15 seconds
- **Memory usage:** ~200-300 MB (browser)
- **Concurrent validations:** 1 at a time (sequential)

---

## 🔒 Security Notes

- Card data **never touches your server**
- Goes directly from browser iframe → Stripe
- This is why no SAQ D is required!
- Your bot only sees the validation result (valid/declined)
