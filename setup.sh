#!/data/data/com.termux/files/usr/bin/bash

echo "🔐 Securing your bot environment..."

# 1. Create secure hidden folder
mkdir -p .secure

# 2. If .env exists, move it. If not, skip.
if [ -f ".env" ]; then
    mv .env .secure/
    echo "✔ .env moved to .secure/"
else
    echo "⚠️ .env not found — skipping move step."
fi

# 3. Apply strict permissions only if .env exists in secure folder
if [ -f ".secure/.env" ]; then
    chmod 600 .secure/.env
    echo "✔ .env permissions locked (600)"
fi

# 4. Lock secure folder
chmod 700 .secure
echo "✔ .secure folder locked (700)"

# 5. Update Python script to load .secure/.env ONLY if find_dotenv exists
if grep -q "find_dotenv" print_bot.py; then
    sed -i 's#find_dotenv()#".secure/.env"#' print_bot.py
    echo "✔ Updated print_bot.py to use .secure/.env"
else
    echo "⚠️ print_bot.py does not use find_dotenv — skipping code update."
fi

echo "🎉 Setup complete!"
echo "🔒 If .env exists, it is now hidden and protected."
echo "➡️ If .env was missing, the script continued without issues."
