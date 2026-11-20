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
echo   IMEI CHECK - Modo Rede Interna (LAN da Empresa)
echo ============================================================
echo.
echo   Envie um dos links abaixo para a equipe abrir no navegador:
".venv\Scripts\python.exe" -c "import socket; h=socket.gethostname(); ips=[ip for ip in socket.gethostbyname_ex(h)[2] if not ip.startswith(('127.', '169.254.'))]; print('\n'.join(f'   -> http://{ip}:8501' for ip in ips) or '   -> Verifique seu IP com ipconfig'); print(f'   -> http://{h}:8501 (nome na rede)')"
echo.
echo   IMPORTANTE:
echo   - Mantenha esta janela aberta enquanto outras pessoas usarem.
echo   - Se outro PC nao carregar, libere a porta 8501 (TCP) no Firewall.
echo   - Para encerrar, feche esta janela ou pressione Ctrl+C.
echo ============================================================
echo.

".venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless false
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel iniciar o IMEI CHECK em rede.
    pause
    exit /b 1
)

exit /b 0
