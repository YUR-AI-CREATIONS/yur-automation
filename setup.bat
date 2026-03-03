@echo off
REM Quick setup script for Superagent framework
REM Run this in PowerShell to configure everything

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  Trinity Superagent Framework - Configuration Setup
echo ============================================================
echo.
echo You have: Trinity API Key ✅
echo           OpenAI API Key (get now)
echo           SendGrid API Key (get now) 
echo           HubSpot API Key (get now)
echo.
echo Total setup time: ~15 minutes
echo.
pause

REM Check if we're in the right directory
if not exist "superagents\requirements.txt" (
    echo ERROR: Must run from F:\New folder\cognitive_engine
    exit /b 1
)

echo.
echo Step 1: Creating .env file...
cd superagents

if exist ".env" (
    echo .env already exists. Backup as .env.bak
    move .env .env.bak
)

REM Copy template
copy .env.example .env
echo ✅ Created superagents\.env

echo.
echo Step 2: Get your API keys (in browser tabs)
echo.
echo   1. OpenAI API Key:
echo      → https://platform.openai.com/api-keys
echo      → Click "Create new secret key"
echo      → Copy (sk-...)
echo.
echo   2. SendGrid API Key:
echo      → https://sendgrid.com/pricing
echo      → Sign up (free)
echo      → Settings → API Keys
echo      → Copy (SG....)
echo      → Verify FROM_EMAIL in Sender Authentication
echo.
echo   3. HubSpot API Key:
echo      → https://app.hubspot.com
echo      → Sign up (free)
echo      → Settings → Private Apps
echo      → Copy Access Token
echo      → Copy Portal ID from Account & Billing
echo.
pause

echo.
echo Step 3: Edit superagents\.env
echo.
echo Open the file and replace:
echo   - sk-...PASTE_YOUR_KEY_HERE... with your OpenAI key
echo   - SG....PASTE_YOUR_KEY_HERE... with your SendGrid key
echo   - pat-...PASTE_YOUR_KEY_HERE... with your HubSpot key
echo   - 12345 with your HubSpot Portal ID
echo   - sales@yourcompany.com with your verified SendGrid email
echo.
echo ⏱️  This takes 5 minutes to copy/paste
echo.

REM Open the file in VS Code or Notepad
if exist "C:\Program Files\Microsoft VS Code\Code.exe" (
    echo Opening .env file in VS Code...
    "C:\Program Files\Microsoft VS Code\Code.exe" .env
) else (
    echo Opening .env file in Notepad...
    notepad .env
)

pause

echo.
echo Step 4: Test configuration
echo.
cd ..
python -c "
import asyncio
import sys
sys.path.insert(0, 'superagents')

from core.config import SuperagentConfig
from core.trinity_client import TrinityClient

print('Loaded configuration:')
SuperagentConfig.print_config()
print('')

async def test():
    print('Testing Trinity connection...')
    trinity = TrinityClient()
    health = await trinity.health_check()
    if health:
        print('✅ Trinity connected successfully')
    else:
        print('❌ Trinity connection failed')
    await trinity.close()

asyncio.run(test())
" 2>nul || (
    echo.
    echo ⚠️  Configuration test failed. Check:
    echo    1. API keys are correct in .env
    echo    2. .env file is in superagents/ directory
    echo    3. Python environment is activated
)

echo.
echo Step 5: Ready to deploy!
echo.
echo Option A - Run locally:
echo    python -m orchestrator
echo.
echo Option B - Run in Docker (recommended):
echo    docker build -t superagents:latest -f superagents\Dockerfile .
echo    docker run -d --name superagents --env-file superagents\.env superagents:latest
echo.
echo Option C - Docker Compose:
echo    docker-compose -f docker-compose.superagents.yml up -d
echo.
pause
