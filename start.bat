@echo off
title TopTop Sunucu Baslatici
color 0A

echo ===================================================
echo [1/3] Arka planda takili kalan eski sunucular temizleniyor...
echo ===================================================
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo ===================================================
echo [2/3] Mutfak (Backend) baslatiliyor... (Port 8000)
echo ===================================================
cd backend
start "TopTop BACKEND" cmd /c "title BACKEND SUNUCUSU && color 0D && echo Mutfak calisiyor! Kapatmak icin bu pencereyi carpidan kapat. && echo. && venv\Scripts\python.exe -m app.main"
cd ..

echo.
echo ===================================================
echo [3/3] Garson (Frontend) baslatiliyor... (Port 5500)
echo ===================================================
cd frontend
start "TopTop FRONTEND" cmd /c "title FRONTEND SUNUCUSU && color 0B && echo Garson calisiyor! Tarayicidan http://127.0.0.1:5500 adresine git. && echo. && python -m http.server 5500"
cd ..

echo.
echo Her sey hazir Kral!
echo 1. Tarayicini ac ve suraya git: http://localhost:5500
echo.
echo Kapatmak istediginde acilan o iki siyah pencereyi carpidan kapatman yeterli.
pause
