@echo off
reg add HKEY_CURRENT_USER\Console /v QuickEdit /t REG_DWORD /d 00000000 /f

echo "Installing cx_Oracle..."
pip install cx_Oracle --user
echo "cx_Oracle installed successfully!"

echo "Installing nbextensions"
pip install jupyter_contrib_nbextensions && jupyter contrib nbextension install --user
echo "nbextensions installed successfully!"

echo "Installing voila"
pip install voila
echo "voila installed successfully!"

echo "All packages have been installed！ Pressing any button to close the window now!"
pause