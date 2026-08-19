#!/usr/bin/env python3
"""Dump getUpdates — use it to find a chat id.

Add the bot to the chat, send any message there, then run this and look for
result[].message.chat.id (group ids are negative).
"""

import json

import requests

from config import REQUEST_TIMEOUT, TELEGRAM_BOT_TOKEN

response = requests.get(
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
    timeout=REQUEST_TIMEOUT,
)
payload = response.json()
print(json.dumps(payload, indent=2, ensure_ascii=False))

for update in payload.get('result', []):
    chat = (update.get('message') or update.get('my_chat_member') or {}).get('chat')
    if chat:
        print(f"\nchat id: {chat['id']}   type: {chat.get('type')}   "
              f"title: {chat.get('title') or chat.get('username', '')}")
