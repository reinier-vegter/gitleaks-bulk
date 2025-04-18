#!/bin/bash

set -e

if [ $(dpkg -l | grep 'patchelf\|ccache' | wc -l) -ne 2 ]; then
    echo 'patchelf / ccache missing, install using `sudo apt install patchelf ccache` .'
    exit 1
else
    echo "========================== Build Ubuntu binary =========================="
    python3 -m venv env
    env/bin/pip install -r requirements.txt
    env/bin/pip install nuitka
    env/bin/python -m nuitka --standalone --onefile --static-libpython=yes --lto=yes --assume-yes-for-downloads --output-dir=dist/ubuntu --output-filename="gitleaks-bulk" main.py
fi

# WSL ?
if (grep -q Microsoft /proc/version || grep -q WSL /proc/sys/kernel/osrelease) && which pip.exe > /dev/null; then
    echo "========================== Build Windows binary (WSL host) =========================="
    venv=$(echo $(cmd.exe /c echo %LOCALAPPDATA% 2>/dev/null  | tr -d '[:space:][:cntrl:]')\\gitleaks-bulk-build-venv |  tr '\\\\' '/')
    lvenv=$(wslpath "$venv")
    [ ! -d "$lvenv" ] && echo "Setting up venv for wsl (${venv})" && python.exe -m venv "$venv" # Build venv if needed
    chmod +x "${lvenv}"/Scripts/*.exe
    "${lvenv}"/Scripts/pip.exe install -r requirements.txt

    "${lvenv}"/Scripts/pip.exe install pyinstaller
    "${lvenv}"/Scripts/pyinstaller.exe --distpath dist/windows --onefile --name gitleaks-bulk.exe main.py

    # "${lvenv}"/Scripts/pip.exe install nuitka
    # "${lvenv}"/Scripts/python.exe -m nuitka --standalone --onefile --lto=yes --mingw64 --jobs=16 --assume-yes-for-downloads --output-dir="$(wslpath -w "$PWD")/dist/windows" --output-filename="gitleaks-bulk.exe" main.py
else
    echo "!! If you are using WSL, make sure to install Pythion with pip on the host, I will use it and it's a bit faster"
    if ! which wine > /dev/null || [ ! -f wenv/Scripts/pip.exe ]; then
        cat << EOF
        wine or pip not found, execute this first:

        sudo dpkg --add-architecture i386
        sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
        sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/$(lsb_release -sc)/winehq-$(lsb_release -sc).sources
        sudo apt update
        sudo apt install --install-recommends winehq-stable mingw-w64 winetricks
        wget https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe -O /tmp/python-installer.exe
        export WINEPREFIX="$PWD"/wenv
        export WINEARCH=win64
        wine /tmp/python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
        wine python -m venv wenv
        winetricks --force --unattended mfc42
EOF
        exit 1
    else
        echo "========================== Build Windows binary (wine) =========================="
        export WINEPREFIX="$PWD"/wenv
        export WINEARCH=win64
        export WINEDEBUG=-all
        export WINE_NUM_THREADS=16
        wine python --version
        wine pip install -r requirements.txt


        wine pip install pyinstaller
        wine pyinstaller --distpath dist/windows --onefile --name gitleaks-bulk.exe main.py

        # wine pip install nuitka
        # wine python -m nuitka --standalone --onefile --lto=yes --mingw64 --clang --jobs=16 --assume-yes-for-downloads --output-dir=dist/windows --output-filename="gitleaks-bulk.exe" main.py
    fi
fi
