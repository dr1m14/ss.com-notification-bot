#!/usr/bin/env python3
"""Watch ss.lv search results and push newly-appeared listings to Telegram.

Works with any ss.lv result page (cars, flats, houses, ...). Columns are read
from the page's own header row, so filters are written against the Latvian
column names shown on the site: 'Gads', 'Cena', 'Ist.', 'm2', 'Stavs', ...
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import (BASE, CHAT_ID, MESSAGE_DELAY, PAGE_DELAY, REQUEST_TIMEOUT,
                    STATE_FILE, TELEGRAM_BOT_TOKEN, USER_AGENT, require_telegram)
from searches import SEARCHES

# Credentials and tunables live in .env (see config.py); the searches themselves
# live in searches.py. Nothing in this file normally needs editing.

HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept-Language': 'lv,en;q=0.8',
}

# --- Logging -----------------------------------------------------------------

def log(message, stream=None):
    """Print one timestamped line.

    flush=True matters under launchd: stdout redirected to a file is block-
    buffered, so without it `tail -f ssbot.log` shows nothing until the run ends
    and stderr lines land out of order.
    """
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{stamp}  {message}", file=stream or sys.stdout, flush=True)

# --- State -------------------------------------------------------------------

def load_seen():
    """Return the set of ss.lv listing ids we've already reported."""
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted(seen), f, indent=0)


# --- Parsing helpers ---------------------------------------------------------

def normalize(text):
    """Fold a column name for lookup: 'm²' -> 'm2', 'Stāvs' -> 'stavs'."""
    text = (text or '').replace('²', '2').replace('³', '3')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', text.lower())


def parse_number(text):
    """First number in the cell, ignoring thousands commas.

    '23,950  €' -> 23950 | '4/5' -> 4 | '133 tūkst.' -> 133 | 'Renov.' -> None
    """
    match = re.search(r'\d[\d,]*', text or '')
    return int(match.group().replace(',', '')) if match else None


def column_names(soup):
    """Map each data-cell index to its header name.

    The header row's first cell spans photo + checkbox + description, so the
    labelled columns start at data index 3. Returns {index: name}.
    """
    header = soup.find('tr', id='head_line')
    if not header:
        return {}

    names, index = {}, 0
    for cell in header.find_all('td'):
        span = int(cell.get('colspan', 1))
        if span == 1:
            names[index] = cell.get_text(' ', strip=True)
        index += span
    return names


# --- Filtering ---------------------------------------------------------------

def matches(row, filters):
    """True if the parsed row satisfies every configured filter."""
    for column, rule in filters.items():
        if column == 'where':
            continue
        key = normalize(column)
        if key not in row['columns']:
            raise KeyError(
                f"No column {column!r} on this page. Available: "
                f"{', '.join(sorted(row['columns']))}"
            )
        text = row['columns'][key]
        number = parse_number(text)

        if 'min' in rule or 'max' in rule:
            if number is None:
                return False
            if 'min' in rule and number < rule['min']:
                return False
            if 'max' in rule and number > rule['max']:
                return False
        if 'equals' in rule and text.strip().lower() != str(rule['equals']).strip().lower():
            return False
        if 'contains' in rule and rule['contains'].lower() not in text.lower():
            return False
        if 'not_contains' in rule and rule['not_contains'].lower() in text.lower():
            return False

    where = filters.get('where')
    if where and not where(row):
        return False
    return True


# --- Scraping ----------------------------------------------------------------

def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')


def parse_row(row, names, search_name):
    """Turn one result <tr> into a listing dict, or None if it isn't one.

    Cells [0] photo, [1] checkbox, [2] description, then one per header column.
    Ad rows (tr_bnr_*) carry a single cell and are skipped by the caller.
    """
    cells = row.find_all('td')
    if len(cells) < 4:
        return None

    link_tag = row.find('a', class_='am')
    if not link_tag or not link_tag.get('href'):
        return None

    columns, display = {}, {}
    for index, name in names.items():
        if index < len(cells):
            value = cells[index].get_text(' ', strip=True)
            columns[normalize(name)] = value
            display[name] = value

    return {
        'id': row['id'][3:],  # strip the 'tr_' prefix
        'search': search_name,
        'title': re.sub(r'\s+', ' ', link_tag.get_text(' ', strip=True)),
        'link': BASE + link_tag['href'],
        'columns': columns,   # normalized keys, for filtering
        'display': display,   # original header names, for output
    }


def find_next_page(soup):
    """href of the 'Nākamie' (next page) link, or None on the last page.

    The anchor wraps an <img>, so it can't be matched on its text alone; it is
    the last rel="next" nav link on the page.
    """
    candidates = soup.find_all('a', class_='navi', rel='next')
    return candidates[-1].get('href') if candidates else None


def scrape(search):
    """Walk every result page of one search, returning listings that pass filters."""
    url = search['url']
    filters = search.get('filters', {})
    listings, seen_ids, seen_pages = [], set(), set()

    for _ in range(search.get('max_pages', 20)):
        if url in seen_pages:
            break
        seen_pages.add(url)

        soup = fetch(url)
        names = column_names(soup)
        if not names:
            raise RuntimeError(f"No header row found on {url} — is that a results page?")

        for element in soup.find_all('tr', id=re.compile(r'^tr_\d+$')):
            listing = parse_row(element, names, search['name'])
            if listing is None or listing['id'] in seen_ids:
                continue
            seen_ids.add(listing['id'])
            if matches(listing, filters):
                listings.append(listing)

        next_href = find_next_page(soup)
        if not next_href:
            break
        url = BASE + next_href
        time.sleep(PAGE_DELAY)  # be polite to ss.lv

    return listings


# --- Output ------------------------------------------------------------------

def visible_fields(listing, show=None):
    """(name, value) pairs to display; 'show' matches accent/case-insensitively."""
    wanted = None if show is None else {normalize(s) for s in show}
    return [(name, value) for name, value in listing['display'].items()
            if (wanted is None or normalize(name) in wanted) and value and value != '-']


def summarize(listing, show=None):
    """'Gads: 2018 | Cena: 23,950 €' for the configured columns."""
    return ' | '.join(f"{n}: {v}" for n, v in visible_fields(listing, show))


def send_telegram_message(message):
    response = requests.post(
        f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
        data={'chat_id': CHAT_ID, 'text': message, 'disable_web_page_preview': 'true'},
        timeout=REQUEST_TIMEOUT,
    )
    payload = response.json()
    if not payload.get('ok'):
        log(f"Telegram error: {payload}", stream=sys.stderr)
    return payload.get('ok', False)


def format_message(listing, show=None):
    lines = [f"🔔 New {listing['search']} listing", listing['title'][:300]]
    lines += [f"{name}: {value}" for name, value in visible_fields(listing, show)]
    lines.append(listing['link'])
    return '\n'.join(lines)


# --- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true',
                    help="print matches, send nothing, don't touch the state file")
    ap.add_argument('--notify-all', action='store_true',
                    help='send every match even if already seen (ignores state)')
    ap.add_argument('--search', action='append',
                    help='only run the named search (repeatable)')
    ap.add_argument('--columns', metavar='URL',
                    help='print the column names of a results page and exit')
    args = ap.parse_args()

    if args.columns:
        names = column_names(fetch(args.columns))
        if not names:
            sys.exit("No header row found — is that an ss.lv results page?")
        log(f"Columns on {args.columns}:")
        for name in names.values():
            log(f"  {name!r}   -> filter key: {normalize(name)!r}")
        return

    searches = [s for s in SEARCHES if s.get('enabled', True)]
    if args.search:
        wanted = {n.lower() for n in args.search}
        searches = [s for s in searches if s['name'].lower() in wanted]
        if not searches:
            sys.exit(f"No search matched {args.search}. "
                     f"Known: {[s['name'] for s in SEARCHES]}")

    seen = load_seen()
    first_run = not seen and not args.notify_all

    found = []
    for search in searches:
        results = scrape(search)
        log(f"{search['name']}: {len(results)} listing(s) matched.")
        found += results

    show_by_search = {s['name']: s.get('show') for s in searches}

    new = [l for l in found if args.notify_all or l['id'] not in seen]
    log(f"{len(new)} new.")
    for listing in new:
        log(f"  {summarize(listing, show_by_search.get(listing['search']))}")
        log(f"    {listing['link']}")

    if args.dry_run:
        log("(dry run: nothing sent, state file untouched)")
        return

    require_telegram()

    if first_run and new:
        # Don't spam the chat with the entire back catalogue on the first run.
        save_seen({l['id'] for l in found})
        log(f"First run: recorded {len(found)} existing listing(s) as a baseline. "
              f"Future runs report only listings added after this.")
        return

    sent = 0
    for listing in new:
        if send_telegram_message(format_message(listing, show_by_search.get(listing['search']))):
            sent += 1
            seen.add(listing['id'])
        time.sleep(MESSAGE_DELAY)  # stay under Telegram's rate limit

    seen.update(l['id'] for l in found)
    save_seen(seen)
    if new:
        log(f"Sent {sent}/{len(new)} message(s).")


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Under launchd an uncaught traceback lands in the log with no timestamp
        # and no context. Mark it, then re-raise so the exit code stays non-zero
        # and `./schedule.sh status` reports the failure.
        log(f"FAILED: {type(error).__name__}: {error}", stream=sys.stderr)
        raise
