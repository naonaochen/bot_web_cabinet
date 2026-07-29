@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo Bot Web Cabinet - Ultra-Fast Build
echo ============================================================
echo.
echo This script builds both CLI and GUI executables.
echo It expects Python, PyInstaller, and dependencies to already be installed.
echo.
echo Notes:
echo   - OCR support requires pytesseract, pillow, and Tesseract.exe at runtime
echo   - settings.yaml is not bundled; place it beside the EXE files
echo   - Build cache is cleared before packaging to avoid stale artifacts
echo ============================================================
echo.

echo [0/4] Checking runtime prerequisites...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    pause
    exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller not installed.
    echo Please run: pip install pyinstaller
    pause
    exit /b 1
)

python -c "import pytesseract; from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo WARN: OCR Python packages not fully available in this environment.
    echo WARN: EXE may fall back to manual captcha input.
) else (
    echo [OK] OCR Python packages detected.
)

tesseract --version >nul 2>&1
if errorlevel 1 (
    echo WARN: Tesseract executable not found in PATH.
    echo WARN: OCR may fall back to manual captcha input.
) else (
    echo [OK] Tesseract executable detected.
)

if not exist efore_favicon.ico (
    echo ERROR: Icon file not found: efore_favicon.ico
    pause
    exit /b 1
)

if not exist config\settings.yaml (
    echo WARN: config\settings.yaml not found in project folder.
    echo WARN: The EXE will use defaults unless you copy settings.yaml beside it.
)

echo [OK] Prerequisites check complete.
echo.

echo [1/4] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
echo [OK] Clean completed.
echo.

echo [2/2] Building GUI version using spec file...
echo Using: RPA_Control_Form_fast.spec
python -m PyInstaller --noconfirm --clean RPA_Control_Form_fast.spec
if errorlevel 1 (
    echo.
    echo ERROR: GUI build failed.
    pause
    exit /b 1
)
echo [OK] GUI version built successfully.
echo.

echo ============================================================
echo Build Completed Successfully!
echo ============================================================
echo.
echo Generated executable:
echo   GUI Version : %cd%\dist\Bot_Web_Cabinet.exe
echo.
echo File size:
for %%F in (dist\Bot_Web_Cabinet.exe) do (
    if exist "%%~fF" (
        set /a size_kb=%%~zF/1024
        echo   Bot_Web_Cabinet.exe : !size_kb! KB
    )
)
echo.

echo Usage:
echo   Bot_Web_Cabinet.exe - GUI mode
necho.
echo IMPORTANT:
echo   1) Copy config\settings.yaml beside the EXE.
echo   2) Install Tesseract OCR if you want automatic captcha recognition.
echo   3) Keep the EXE and settings.yaml in the same folder for runtime overrides.
echo.
pause
