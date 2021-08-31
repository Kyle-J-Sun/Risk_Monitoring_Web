@echo off
reg add HKEY_CURRENT_USER\Console /v QuickEdit /t REG_DWORD /d 00000000 /f

echo "Launching Jupyter Lab"
pushd "%~dp0"
cd ..
jupyter lab

