@echo off
title Arrivata Sales Tool
echo.
echo  ===================================
echo   Arrivata Sales Tool
echo  ===================================
echo.

REM Check if .env exists, if not copy from example
if not exist ".env" (
    echo  Creando archivo .env desde .env.example...
    copy .env.example .env
    echo  Editá el archivo .env y agrega tu ANTHROPIC_API_KEY.
    echo.
)

REM Install dependencies
echo  Instalando dependencias...
pip install -r requirements.txt --quiet

echo.
echo  Iniciando servidor en http://localhost:5001
echo  Presioná Ctrl+C para detener.
echo.

REM Open browser after 2 seconds
start "" /b cmd /c "timeout /t 2 /nobreak > nul && start http://localhost:5001"

python app.py
pause
