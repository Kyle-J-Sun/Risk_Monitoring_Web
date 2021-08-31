@echo off
reg add HKEY_CURRENT_USER\Console /v QuickEdit /t REG_DWORD /d 00000000 /f

echo "Two extensions is installing in order to show interactive widgets in Jupyter Lab..."
cd ..

echo "Installing Node.js..."
conda install nodejs
echo "Installed successfully!"

echo "Installing labextension for the use of widgets..."
jupyter labextension install @jupyter-widgets/jupyterlab-manager
echo "Installing successfully!"

echo "ALL EXTENSIONS HAVE BEEN INSTALLED SUCCESSFULLY!"