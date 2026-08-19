"""Configuration loading for ssbot.

Secrets live in a .env file next to this module (git-ignored). Real environment
variables always win, so you can override any value for a single run:

    TELEGRAM_CHAT_ID=480979058 python parser.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(HERE, '.env')

# Lives here rather than in parser.py so searches.py can use it without the two
# importing each other.
BASE = 'https://www.ss.com'


def load_env(path=ENV_FILE):
    """Read KEY=VALUE lines from .env into os.environ without overwriting it.

    Understands blank lines, '#' comments (whole-line and trailing), optional
    'export ' prefixes, and values wrapped in single or double quotes. Quoting a
    value keeps any '#' inside it. Deliberately dependency-free so the bot still
    starts if nobody ran install.sh.
    """
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return False

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[len('export '):]

        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        else:
            # Unquoted: a ' #' starts a trailing comment, as in a shell.
            value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
        # A real environment variable beats the file.
        os.environ.setdefault(key, value)
    return True


load_env()

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()

# Hints shown if a credential is missing when something actually needs it.
_HINTS = {
    'TELEGRAM_BOT_TOKEN': 'Create a bot or reissue a token with @BotFather on Telegram.',
    'TELEGRAM_CHAT_ID': 'Add the bot to your chat, send a message, then run test2.py '
                        'to see the id.',
}


def require_telegram():
    """Exit with an instruction if credentials are missing.

    Checked at the point of use rather than on import, so --dry-run, --columns
    and wizard.py work with no .env at all.
    """
    missing = [name for name, value in (('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN),
                                        ('TELEGRAM_CHAT_ID', CHAT_ID)) if not value]
    if missing:
        sys.exit(
            f"Missing {' and '.join(missing)}.\n"
            f"  Copy .env.example to .env and fill it in:\n"
            f"    cp .env.example .env\n"
            + ''.join(f"  {_HINTS[name]}\n" for name in missing)
        )

# Optional knobs, overridable from .env.
STATE_FILE = os.environ.get('SSBOT_STATE_FILE') or os.path.join(HERE, 'seen_listings.json')
REQUEST_TIMEOUT = int(os.environ.get('SSBOT_REQUEST_TIMEOUT', '30'))
PAGE_DELAY = float(os.environ.get('SSBOT_PAGE_DELAY', '1.0'))
MESSAGE_DELAY = float(os.environ.get('SSBOT_MESSAGE_DELAY', '0.5'))
USER_AGENT = os.environ.get('SSBOT_USER_AGENT') or (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
)
