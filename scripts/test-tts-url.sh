#!/bin/bash
# Test TTS URL: trigger TTS, extract URL from log, verify fetch
# Usage: ./scripts/test-tts-url.sh

set -e
cd /workspaces/wiim
source /home/vscode/.local/ha-venv/bin/activate

HA_URL=$(grep HA_URL scripts/test.config | cut -d= -f2)
HA_TOKEN=$(grep HA_TOKEN scripts/test.config | cut -d= -f2)
LOG=/workspaces/core/config/home-assistant.log

echo "=== 1. Trigger TTS ==="
curl -s -X POST "$HA_URL/api/services/media_player/play_media" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"media_player.master_bedroom","media_content_id":"media-source://tts/tts.google_translate_en_com?message=UrlTest&cache=false","media_content_type":"music","announce":true}' > /dev/null

sleep 1
echo "=== 2. Extract URL from HA log ==="
URL=$(grep "Playing notification" "$LOG" | tail -1 | sed 's/.*: http/http/' | sed 's/ .*//')
echo "URL: $URL"

if [ -z "$URL" ]; then
  echo "ERROR: No URL found in log"
  exit 1
fi

echo "=== 3. Test fetch (from this machine) ==="
CODE=$(curl -s -o /tmp/tts_verify.mp3 -w "%{http_code}" "$URL")
SIZE=$(wc -c < /tmp/tts_verify.mp3)
echo "HTTP $CODE, $SIZE bytes"

if [ "$CODE" = "200" ] && [ "$SIZE" -gt 1000 ]; then
  echo "OK: URL is fetchable, valid audio size"
else
  echo "FAIL: URL returned $CODE or small size ($SIZE bytes)"
fi

echo "=== 4. Host in URL (WiiM uses this) ==="
echo "$URL" | grep -oE 'http://[^/]+' || true
