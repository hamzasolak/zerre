@echo off
chcp 65001 >nul
title ZERRE — Optofluidik AI Simulasyon ve Dijital Ikiz Sunucusu
color 0B

:: Betigin bulundugu klasore gec (bosluklu klasor yollarini destekler)
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ==========================================================
echo   ZERRE v2.7 — Canli Simulasyon Baslatiliyor...
echo ==========================================================

:: Python kurulumunu kontrol et (python veya py launcher)
where python >nul 2>nul
if %errorlevel%==0 (
    python start_server.py
    goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 start_server.py
    goto :end
)

color 0C
echo.
echo [HATA] Sistemde Python bulunamadi!
echo Lutfen Python 3 kurun veya PATH ortam degiskenine ekleyin.
echo.
pause
exit /b 1

:end
if %errorlevel% neq 0 (
    echo.
    echo [UYARI] Sunucu beklenmedik bir sekilde kapandi.
    pause
)
