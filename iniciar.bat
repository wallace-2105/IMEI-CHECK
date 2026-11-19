@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [AVISO] Ambiente virtual nao encontrado.
    echo Execute primeiro o arquivo "instalar.bat" para preparar o sistema.
    pause
    exit /b 1
)

echo ============================================================
echo   Iniciando IMEI CHECK...
echo   O navegador abrira automaticamente em instantes.
echo   Para encerrar o sistema, feche esta janela ou pressione Ctrl+C.
echo ============================================================
echo.

".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel iniciar o IMEI CHECK.
    pause
    exit /b 1
)

exit /b 0
