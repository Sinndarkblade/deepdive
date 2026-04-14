@echo off
echo Installing DeepDive dependencies...
pip install -r requirements.txt
echo.
echo Done. Start the server with:
echo   python server\app.py
echo.
echo Then open: http://localhost:8766/board
echo Configure your AI provider at: http://localhost:8766/settings
pause
