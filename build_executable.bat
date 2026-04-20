@echo off
echo Starting Portable TradeBot Executable Build...
echo.

cd /d "E:\TradeBot"

echo Creating virtual environment for clean build...
python -m venv build_env
call build_env\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing requirements...
pip install -r requirements.txt

echo.
echo Compiling app.py (Main Trading Bot)...
pyinstaller --onefile --name "TradeBot_App" app.py

echo.
echo Compiling alpaca_paper_bot.py (Alpaca Paper Bot)...
pyinstaller --onefile --name "TradeBot_Alpaca" alpaca_paper_bot.py

echo.
echo Cleaning up build files...
rmdir /s /q build
copy dist\TradeBot_App.exe .\
copy dist\TradeBot_Alpaca.exe .\
rmdir /s /q dist
del /q *.spec

echo.
echo Deactivating and removing virtual environment...
deactivate
rmdir /s /q build_env

echo.
echo Build Complete! The portable programs TradeBot_App.exe and TradeBot_Alpaca.exe are now in the E:\TradeBot directory.
echo You can move these .exe files to any computer and run them directly.
pause
