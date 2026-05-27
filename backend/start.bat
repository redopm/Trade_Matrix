@echo off
echo ====================================================
echo   TradeMatrix Backend Startup
echo ====================================================

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Create required directories
if not exist "database" mkdir database
if not exist "logs" mkdir logs

REM Start FastAPI server
echo Starting FastAPI server on http://localhost:8000
echo Docs available at: http://localhost:8000/docs
echo.
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
