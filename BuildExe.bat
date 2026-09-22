@echo off
cd /d "%~dp0"

echo Closing any running copy of the app first (so it saves its data properly)...
taskkill /IM MyFavoriteThings.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Building MyFavoriteThings.exe ...
python -m PyInstaller --noconfirm --onedir --windowed --name "MyFavoriteThings" app.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo Copying ffmpeg binaries...
copy /Y ffmpeg.exe dist\MyFavoriteThings\ >nul
copy /Y ffplay.exe dist\MyFavoriteThings\ >nul
copy /Y ffprobe.exe dist\MyFavoriteThings\ >nul

echo Linking data folder so the exe uses your real music/journals/favorites...
if exist "dist\MyFavoriteThings\MyFavoriteThingsData" rmdir "dist\MyFavoriteThings\MyFavoriteThingsData"
mklink /J "dist\MyFavoriteThings\MyFavoriteThingsData" "%~dp0MyFavoriteThingsData" >nul

echo.
echo Done! Your app is at: dist\MyFavoriteThings\MyFavoriteThings.exe
echo You can copy the whole "dist\MyFavoriteThings" folder anywhere (or to another PC)
echo and it will run standalone, no Python required.
pause
