#!/bin/bash
# Build WiiM play URL command with fresh TTS.
# WiiM does NOT support playPromptUrl (returns "unknown command"). Use setPlayerCmd:play instead.
# WiiM must be on Network source for URL playback - script switches first.
# Usage: ./scripts/wiim-play-tts-url.sh [WIIM_IP]
# Output: Full URL to curl from Windows. Run STEP 1 first if WiiM is on Spotify etc.

set -e
cd /workspaces/wiim
source /home/vscode/.local/ha-venv/bin/activate

WIIM_IP="${1:-192.168.1.116}"
HA_URL=$(grep HA_URL scripts/test.config | cut -d= -f2)
HA_TOKEN=$(grep HA_TOKEN scripts/test.config | cut -d= -f2)
LOG=/workspaces/core/config/home-assistant.log

# 1. Trigger TTS
curl -s -X POST "$HA_URL/api/services/media_player/play_media" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"media_player.master_bedroom","media_content_id":"media-source://tts/tts.google_translate_en_com?message=UrlTest&cache=false","media_content_type":"music","announce":true}' > /dev/null

sleep 1

# 2. Extract TTS URL from HA log
TTS_URL=$(grep "Playing notification" "$LOG" | tail -1 | sed 's/.*: http/http/' | sed 's/ .*//')
if [ -z "$TTS_URL" ]; then
  echo "ERROR: No TTS URL found in log" >&2
  exit 1
fi

# 3. URL-encode the TTS URL
ENCODED=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$TTS_URL")

# 4. Build WiiM URLs (WiiM uses setPlayerCmd:play for URL playback, NOT playPromptUrl)
echo "# STEP 1: Switch to Network first (required - URL playback only works on Network source):"
echo "curl \"http://${WIIM_IP}/httpapi.asp?command=setPlayerCmd:switchmode:wifi\""
echo ""
echo "# STEP 2: Wait 1 second, then play TTS (setPlayerCmd:play - WiiM does not support playPromptUrl):"
echo "curl \"http://${WIIM_IP}/httpapi.asp?command=setPlayerCmd:play:${ENCODED}\""
echo ""
echo "# Or as single URL (play only, if already on Network):"
echo "http://${WIIM_IP}/httpapi.asp?command=setPlayerCmd:play:${ENCODED}"
