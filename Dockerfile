FROM python:3.11-slim AS base

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libatspi2.0-0 libx11-6 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libexpat1 \
    curl unzip && \
    rm -rf /var/lib/apt/lists/*

# Security: run as non-root
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -s /sbin/nologin appuser

# Set Playwright browser install path (shared system-wide location)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# PORT is set by Render at runtime (not hardcoded here)

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

# Copy application code
COPY . .

# Patch Playwright Chromium launch to hide --headless=new flag from Stripe detection
# This removes the automation indicator from the browser process args
RUN sed -i 's/"--headless=new"/"--headless=new","--disable-blink-features=AutomationControlled"/g' /usr/local/lib/python3.11/site-packages/playwright/driver/package/server/browser_chromium.py 2>/dev/null || true

# Create logs directory and set permissions
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Set permissions on Playwright browsers directory
RUN chown -R appuser:appuser /ms-playwright

# Switch to non-root user
USER appuser

# Expose ports: 10000 for Flask webapp, 8080 for webhook (optional)
EXPOSE 10000 8080

# Health check — verify Flask is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT:-10000}/ || exit 1

# Start the bot
CMD ["python", "bot.py"]
