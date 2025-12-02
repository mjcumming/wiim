#!/usr/bin/env python3
"""
Browser-based test for sleep timer and alarms using Home Assistant UI.
This script uses the browser to navigate HA and test services.
"""

import time

# Note: This would require browser automation setup
# For now, let's use the API approach with token input

print(
    """
To test sleep timer and alarms on the master bedroom device, you need to:

1. Get your Home Assistant access token:
   - Open http://localhost:8123 in your browser
   - Log in
   - Click your profile (bottom left)
   - Scroll to "Long-Lived Access Tokens"
   - Click "Create Token"
   - Copy the token

2. Run the test script:
   export HA_TOKEN='your_token_here'
   python3 scripts/test-timers-interactive.py

Or provide the token directly:
   python3 scripts/test-timers-interactive.py --token YOUR_TOKEN
"""
)
