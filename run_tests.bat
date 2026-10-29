@echo off
echo ================================
echo Work-Life Balance Manager Tests
echo ================================

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Could not activate the virtual environment.
    pause
    exit /b 1
)

py -m unittest discover -s tests -v

if errorlevel 1 (
    echo.
    echo TESTS FAILED. Review the errors above.
) else (
    echo.
    echo ALL TESTS PASSED.
)

pause