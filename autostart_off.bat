@echo off
chcp 65001 >nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CampsiteWeb.lnk" && echo autostart OFF
pause
