@echo off
:: Inicia el Gateway LAN LLM
:: Copiar este archivo a:
::   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\

:: Cambiar al directorio del proyecto
cd /d "c:\Users\APRENDIZ.ITAAPR10712143\Desktop\CLI y API KEY\OLLAMA API AI"

:: Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

:: Iniciar el gateway
start "" uvicorn app.main:app --host 0.0.0.0 --port 8000
