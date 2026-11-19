@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================================
echo   IMEI CHECK - Instalacao do Ambiente Local (100%% Gratuito)
echo ============================================================
echo.

set "PYTHON_EXE="
set "PYTHON_ARGS="

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>&1
    if !errorlevel!==0 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /I "WindowsApps" >nul
        if errorlevel 1 (
            "%%P" -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>&1
            if !errorlevel!==0 if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
        )
    )
)

if not defined PYTHON_EXE (
    for %%D in (
        "%LOCALAPPDATA%\Python\bin\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) do (
        if exist "%%~D" (
            "%%~D" -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>&1
            if !errorlevel!==0 if not defined PYTHON_EXE set "PYTHON_EXE=%%~D"
        )
    )
)

if not defined PYTHON_EXE (
    echo [ERRO] Python 3.11 ou superior nao encontrado neste computador.
    echo Instale o Python em https://www.python.org/downloads/ e tente novamente.
    pause
    exit /b 1
)

echo [1/4] Python encontrado: "%PYTHON_EXE%" %PYTHON_ARGS%

if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Criando ambiente virtual local (.venv)...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual .venv.
        pause
        exit /b 1
    )
) else (
    echo [2/4] Ambiente virtual .venv ja existe.
)

echo [3/4] Instalando dependencias gratuitas (requirements.txt)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias Python. Verifique sua conexao com a internet.
    pause
    exit /b 1
)

echo [4/4] Inicializando banco SQLite e baixando base Osmocom TAC Database...
".venv\Scripts\python.exe" -m services.bootstrap --with-community
if errorlevel 1 (
    echo [AVISO] Nao foi possivel baixar a base online agora.
    echo O sistema foi instalado e voce podera baixar a base pela aba "Banco de dados".
)

echo.
echo ============================================================
echo   Instalacao concluida! Execute "iniciar.bat" para abrir.
echo ============================================================
pause
exit /b 0
