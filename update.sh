#!/data/data/com.termux/files/usr/bin/sh
# Run this from inside the favorite_things_app folder in Termux whenever
# Claude says there's a new version to pull down.
git pull
cd mobile_app
pip install -r requirements.txt
echo "Updated. Restart the server (Ctrl+C, then: python server.py) to apply changes."
