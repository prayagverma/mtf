@echo off
REM One-shot Cloudflare Pages deploy for the MTF Analytics dashboard.
REM Requires wrangler (npm i -g wrangler) + `wrangler login` once.
setlocal
cd /d "%~dp0"

set PROJECT=mtf

where wrangler >nul 2>nul
if errorlevel 1 (
  echo wrangler not found. Install with:  npm i -g wrangler
  exit /b 1
)

echo Deploying %CD% to Cloudflare Pages project '%PROJECT%'...
wrangler pages deploy . --project-name %PROJECT% %*
