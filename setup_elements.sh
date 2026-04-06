@echo off
echo ========================================
echo Stripe Elements Setup Script
echo ========================================
echo.

echo Step 1: Installing Python dependencies...
pip install flask playwright
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo Step 2: Installing Playwright browsers...
playwright install chromium
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install Playwright browsers
    pause
    exit /b 1
)
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Add your Stripe Publishable Key to .env
echo    Get it from: https://dashboard.stripe.com/apikeys
echo.
echo 2. Start the webapp: python -m webapp.app
echo.
echo 3. Start the bot: python bot.py
echo.
pause
