#!/usr/bin/env python3
"""Interactively build a SEARCHES entry for any ss.lv results page.

    python wizard.py https://www.ss.com/lv/transport/cars/bmw/x3/sell/

Reads the page's own columns, shows you the real values in each, asks what you
want to filter on, previews how many listings match, and prints a SEARCHES block
to paste into searches.py.

Only offers filters parser.py can actually apply — i.e. the columns of the
results table. Filters that exist on ss.lv's search form but never appear as a
column (Ātrumkārba, Virsbūve, Krāsa) are not offered, because nothing on the
results page carries them.
"""

import argparse
import re
import sys
from collections import Counter

import parser as ssbot

# Fuel type is not a column of its own; ss.lv encodes it as a suffix on Tilpums.
# Each entry carries the live rule and the source text to print, kept in step.
FUEL_RULES = [
    ('Any', None, None, None, None),
    ('Dīzelis (diesel)', {'contains': 'D'}, "{'contains': 'D'}", None, None),
    ('Benzīns (petrol)', None, None,
     lambda row: row['columns']['tilpums'][-1:].isdigit(),
     "lambda row: row['columns']['tilpums'][-1:].isdigit()"),
    ('Hibrīds (hybrid)', {'contains': 'H'}, "{'contains': 'H'}", None, None),
    ('Elektriskais (electric)', {'equals': 'E'}, "{'equals': 'E'}", None, None),
    ('Exact value (e.g. 2.0D)', 'ASK', None, None, None),
]


def ask(prompt, default=''):
    """One line of input, with Ctrl-C and EOF treated as 'stop'."""
    try:
        answer = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)
    return answer or default


def ask_choice(prompt, options, default=1):
    """Numbered menu; returns the 1-based index chosen."""
    for number, label in enumerate(options, 1):
        print(f"    {number}) {label}")
    while True:
        raw = ask(f"  {prompt} [{default}]: ", str(default))
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"  Enter a number between 1 and {len(options)}.")


def ask_number(prompt):
    """A whole number, or blank for 'no limit'."""
    while True:
        raw = ask(prompt)
        if not raw:
            return None
        cleaned = raw.replace(',', '').replace(' ', '')
        if cleaned.lstrip('-').isdigit():
            return int(cleaned)
        print("  Enter a whole number, or leave blank for no limit.")


# Units ss.lv appends to otherwise-numeric cells.
UNIT_TOKENS = ('tūkst.', 'tūkst', '€', 'm²', 'm2', 'km', 'gab.')


def is_numeric_value(value):
    """True only if the cell is a number plus separators and a known unit.

    parse_number() alone is not enough to classify a column: 'Hospitāļu 49' has
    a number in it, but a min/max on a street name is nonsense. Requiring that
    nothing but digits, separators and units remain keeps addresses as text
    while '23,950 €', '133 tūkst.' and '4/5' stay numeric.
    """
    text = value
    for unit in UNIT_TOKENS:
        text = text.replace(unit, '')
    return re.sub(r'[\d\s,./-]', '', text) == '' and any(c.isdigit() for c in value)


def describe_column(name, values):
    """Classify a column from its real values and print a summary."""
    present = [v for v in values if v and v != '-']
    numbers = [n for n in (ssbot.parse_number(v) for v in present) if n is not None]
    numeric = bool(present) and sum(map(is_numeric_value, present)) >= 0.7 * len(present)
    is_fuel = ssbot.normalize(name) == 'tilpums'

    counts = Counter(present)
    distinct = len(counts)

    print(f"\n  Column: {name}   ({'numeric' if numeric and not is_fuel else 'text'}, "
          f"{distinct} distinct value{'s' if distinct != 1 else ''})")
    # Tilpums parses as a number ('2.0D' -> 2), but that range is meaningless —
    # it is an engine code, so don't advertise it as one.
    if numeric and numbers and not is_fuel:
        print(f"    range: {min(numbers)} – {max(numbers)}")
    if distinct <= 12:
        print("    values: " + ", ".join(f"{v} ({n})" for v, n in counts.most_common()))
    else:
        print("    common: " + ", ".join(f"{v} ({n})" for v, n in counts.most_common(6)) + ", …")
    # ss.lv writes mileage as '133 tūkst.', so min/max compare thousands.
    if any('tūkst' in v for v in present[:50]):
        print("    note: values are in thousands — enter 150 to mean 150 000")
    return numeric and not is_fuel


def build_rule(name, numeric):
    """Ask how to filter one column.

    Returns (rule, rule_source, where, where_source) — the live objects used for
    the preview and the source text printed in the snippet, built together so
    the two can never drift. Nothing here is eval'd.
    """
    # Fuel shortcut, since 'Dzinējs' on ss.lv's form has no column of its own.
    if ssbot.normalize(name) == 'tilpums':
        print("    (fuel type is the suffix on this column)")
        choice = ask_choice("Dzinējs / fuel type?", [e[0] for e in FUEL_RULES], default=1)
        label, rule, rule_src, where, where_src = FUEL_RULES[choice - 1]

        if rule == 'ASK':
            text = ask("    exact value (e.g. 2.0D): ")
            if not text:
                return None, None, None, None
            print(f"    -> exactly {text}")
            return {'equals': text}, "{" + f"'equals': {text!r}" + "}", None, None

        if rule or where:
            print(f"    -> {label}")
            return rule, rule_src, where, where_src
        return None, None, None, None

    if numeric:
        if ask_choice("Filter?", ['Any', 'Set a range (min/max)'], default=1) == 1:
            return None, None, None, None
        low = ask_number("    min (blank = no limit): ")
        high = ask_number("    max (blank = no limit): ")
        rule = {}
        if low is not None:
            rule['min'] = low
        if high is not None:
            rule['max'] = high
        if not rule:
            return None, None, None, None
        source = "{" + ", ".join(f"'{k}': {v}" for k, v in rule.items()) + "}"
        return rule, source, None, None

    choice = ask_choice("Filter?", ['Any', 'contains', 'equals', 'does not contain'], default=1)
    if choice == 1:
        return None, None, None, None
    text = ask("    text: ")
    if not text:
        return None, None, None, None
    key = {2: 'contains', 3: 'equals', 4: 'not_contains'}[choice]
    return {key: text}, "{" + f"'{key}': {text!r}" + "}", None, None


def render(name, url, filters, where, show, max_pages):
    """Produce the pasteable SEARCHES entry."""
    lines = ["    {", f"        'name': {name!r},"]
    if url.startswith(ssbot.BASE):
        lines.append(f"        'url': BASE + {url[len(ssbot.BASE):]!r},")
    else:
        lines.append(f"        'url': {url!r},")

    if filters or where:
        lines.append("        'filters': {")
        for column, rule in filters.items():
            lines.append(f"            {column!r}: {rule},")
        if where:
            lines.append(f"            'where': {where},")
        lines.append("        },")
    else:
        lines.append("        'filters': {},")

    lines.append(f"        'show': {show!r},")
    lines.append(f"        'max_pages': {max_pages},")
    lines.append("    },")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('url', help='an ss.lv results page, e.g. .../cars/bmw/x3/sell/')
    ap.add_argument('--max-pages', type=int, default=20,
                    help='how many result pages to scan (default 20)')
    args = ap.parse_args()

    if not sys.stdin.isatty():
        sys.exit("wizard.py is interactive — run it from a terminal.")

    url = args.url.strip()
    if '/sell/' not in url and '/hand_over/' not in url and '/buy/' not in url:
        print("Note: this URL has no deal type, so it mixes sales with rentals.")
        print("      Consider adding /sell/ (or /hand_over/ for rent).\n")

    print(f"Reading {url} …")
    listings = ssbot.scrape({'name': 'wizard', 'url': url, 'filters': {},
                             'max_pages': args.max_pages})
    if not listings:
        sys.exit("No listings found there — is it an ss.lv results page?")

    names = list(listings[0]['display'].keys())
    print(f"Found {len(listings)} listings and {len(names)} filterable columns: "
          + ", ".join(names))
    print("\nFor each column: press Enter to accept the default and skip it.")

    live, sources = {}, {}          # live: real rules for the preview
    where_source = None             # sources: matching text for the snippet
    for name in names:
        numeric = describe_column(name, [l['display'].get(name, '') for l in listings])
        rule, rule_source, where, where_src = build_rule(name, numeric)
        if rule:
            live[name] = rule
            sources[name] = rule_source
        if where:
            live['where'] = where
            where_source = where_src

    # Preview against the listings already fetched — no extra requests.
    matched = [l for l in listings if ssbot.matches(l, live)]
    print(f"\n{'=' * 66}")
    print(f"{len(matched)} of {len(listings)} listings match.")
    for listing in matched[:5]:
        print("  " + " | ".join(f"{k}: {v}" for k, v in listing['display'].items()
                                if v and v != '-'))
    if len(matched) > 5:
        print(f"  … and {len(matched) - 5} more")

    if not matched:
        print("\nNothing matches — the filters are probably too strict.")

    default_name = url.rstrip('/').split('/')[-2].replace('-', ' ').title()
    name = ask(f"\nName for this search [{default_name}]: ", default_name)
    show = ask(f"Columns to show, comma-separated [{', '.join(names)}]: ")
    show_list = [s.strip() for s in show.split(',') if s.strip()] or names

    print(f"\n{'=' * 66}")
    print("Paste this into the SEARCHES list in searches.py:\n")
    print(render(name, url, sources, where_source, show_list, args.max_pages))
    print(f"\n{'=' * 66}")
    print("Then check it with:  python parser.py --dry-run")


if __name__ == '__main__':
    main()
