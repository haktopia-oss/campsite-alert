@echo off
chcp 65001 >nul
curl -s -X POST http://127.0.0.1:8765/api/quit >nul && echo stopped || echo not running
pause
