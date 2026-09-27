#!/bin/bash
# Double-click this file to open Email Sorter.
cd "$(dirname "$0")"

# Prefer the python.org install: Apple's built-in Python has a broken window toolkit.
for py in /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c "import tkinter" >/dev/null 2>&1; then
        echo "Starting Email Sorter... (keep this window open while it runs)"
        if ! "$py" email_sorter_app.py; then
            echo
            echo "Something went wrong. Please take a screenshot of this window."
            read -r -p "Press Enter to close."
        fi
        exit
    fi
done

osascript -e 'display dialog "Python needs to be installed first (it is free).\n\n1. Your browser will open the Python download page.\n2. Download and install it for macOS.\n3. Then double-click \"Start (Mac)\" again." buttons {"OK"} default button "OK" with title "Email Sorter"'
open "https://www.python.org/downloads/"
