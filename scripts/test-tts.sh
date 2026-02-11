#!/bin/bash
# Simple TTS test script
# Usage: ./test-tts.sh "Your message here" [entity_id]

MESSAGE="${1:-Hello, this is a test}"
ENTITY="${2:-media_player.master_bedroom}"

# Load config
source /home/vscode/.local/ha-venv/bin/activate
cd /workspaces/wiim

# Read config
HA_URL=$(grep HA_URL scripts/test.config | cut -d= -f2)
HA_TOKEN=$(grep HA_TOKEN scripts/test.config | cut -d= -f2)

# URL encode the message
ENCODED_MSG=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$MESSAGE'))")

echo "Sending TTS: '$MESSAGE'"
echo "To: $ENTITY"

curl -s -X POST "$HA_URL/api/services/media_player/play_media" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"entity_id\": \"$ENTITY\",
    \"media_content_id\": \"media-source://tts/tts.google_translate_en_com?message=$ENCODED_MSG&cache=false\",
    \"media_content_type\": \"music\",
    \"announce\": true
  }" && echo -e "\n✅ TTS sent!"
