#!/usr/bin/env python3
"""Send one test message — confirms the token and chat id in .env work."""

import requests

from config import CHAT_ID, REQUEST_TIMEOUT, TELEGRAM_BOT_TOKEN

response = requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
    data={'chat_id': CHAT_ID, 'text': "Test message from ssbot"},
    timeout=REQUEST_TIMEOUT,
)
print(response.json())
