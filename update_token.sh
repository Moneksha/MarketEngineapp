#!/bin/bash

# =========================================================================
# Market Engine - Daily Token Updater
# =========================================================================

# Path to the file where you paste the daily request token
TOKEN_FILE="/var/www/market-engine/kite_token.txt"

# Go to backend directory
cd /var/www/market-engine/backend || exit

# Check if file exists and has content
if [ ! -s "$TOKEN_FILE" ]; then
    echo "❌ Error: $TOKEN_FILE is missing or empty."
    echo "Please paste today's request token into $TOKEN_FILE and try again."
    exit 1
fi

# Read the token from the file (handles potential whitespace/newlines)
REQUEST_TOKEN=$(cat "$TOKEN_FILE" | tr -d ' \n\r')

echo "🔄 Found request token, exchanging for access token..."

# Run the python script to exchange the token and update .env
source venv/bin/activate
python update_token.py "$REQUEST_TOKEN"

if [ $? -eq 0 ]; then
    echo "✅ Token exchanged successfully!"
    echo "🔄 Restarting Market Engine backend service..."
    sudo systemctl restart market-engine
    
    echo "🧹 Cleaning up $TOKEN_FILE..."
    > "$TOKEN_FILE"
    
    echo "🚀 Done! Market Engine is using the new token."
else
    echo "❌ Failed to exchange token. Check your API keys and try again."
fi
