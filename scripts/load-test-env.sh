#!/bin/bash
# Load testing environment variables
# Usage: source scripts/load-test-env.sh

if [ -f "scripts/test.config" ]; then
    export $(cat scripts/test.config | grep -v '^#' | xargs)
    echo "✅ Testing environment loaded from scripts/test.config"
    echo "   HA_URL: $HA_URL"
    echo "   HA_TOKEN: ${HA_TOKEN:0:20}... (${#HA_TOKEN} chars)"
elif [ -f ".env.testing" ]; then
    export $(cat .env.testing | grep -v '^#' | xargs)
    echo "✅ Testing environment loaded from .env.testing"
    echo "   HA_URL: $HA_URL"
    echo "   HA_TOKEN: ${HA_TOKEN:0:20}... (${#HA_TOKEN} chars)"
else
    echo "❌ Configuration file not found!"
    echo "   Looking for: scripts/test.config or .env.testing"
    echo "   Create scripts/test.config with:"
    echo "     HA_URL=http://localhost:8123"
    echo "     HA_TOKEN=your_token_here"
    exit 1
fi
