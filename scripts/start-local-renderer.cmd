@echo off
setlocal
cd /d "%~dp0\.."
if not exist node_modules call npm install
node local-renderer\server.mjs
