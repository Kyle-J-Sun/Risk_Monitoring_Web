@echo off
reg add HKEY_CURRENT_USER\Console /v QuickEdit /t REG_DWORD /d 00000000 /f

echo "Launching Voila"
cd Code
rd /s/q .ipynb_checkpoints
rd /s/q __pycache__

voila --show_tracebacks=True

@REM voila --template=gridstack
@REM voila --template=gridstack --VoilaConfiguration.resources='{"gridstack": {"show_handles": True}}'
@REM voila --template=gridstack liquidity.ipynb --VoilaConfiguration.resources="{'gridstack': {'show_handles': True}}"