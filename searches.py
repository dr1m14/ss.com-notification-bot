"""Your searches — the only file you normally edit.

Each entry: where to look, what to call it, and which columns to filter on.
Filter keys are the column names from the page's own header row, matched case-
and accent-insensitively, so 'm²' == 'm2' and 'Stāvs' == 'Stavs'.

Per column: min, max, contains, not_contains, equals.
'where' is an escape hatch: a callable taking the parsed row, whose
row['columns'] uses normalized keys ('stavs', 'm2', 'tilpums').

Build one interactively instead of by hand:
    python wizard.py https://www.ss.com/lv/transport/cars/bmw/x3/sell/

Run `python parser.py --dry-run` after editing.
"""

from config import BASE

SEARCHES = [
    {
        'name': 'BMW X3',
        'url': BASE + '/lv/transport/cars/bmw/x3/sell/',
        'filters': {
            'Gads': {'min': 2018},
            # Dzinējs = Dīzelis. The results table has no engine-type column;
            # fuel is the suffix on Tilpums — 2.0D/3.0D diesel, 2.0/3.0 petrol,
            # 2.0H hybrid, E electric. Delete this line to allow every fuel type.
            'Tilpums': {'contains': 'D'},
        },
        # Columns to show in the notification (omit for all of them).
        'show': ['Gads', 'Tilpums', 'Nobraukums', 'Cena'],
        'max_pages': 20,
    },

    # --- More examples; set 'enabled': True to switch one on. ----------------
    {
        'name': 'Riga centre flats',
        'url': BASE + '/lv/real-estate/flats/riga/centre/sell/',
        'enabled': False,
        'filters': {
            'Ist.': {'min': 2, 'max': 4},
            'm2': {'min': 50},
            'Cena': {'max': 250000},
            'Stavs': {'min': 2},                    # '4/5' compares on the 4
            'Serija': {'not_contains': 'Hrušč'},
        },
        'show': ['Iela', 'Ist.', 'm2', 'Stavs', 'Serija', 'Cena'],
        'max_pages': 20,
    },
    {
        'name': 'LED TVs under 300',
        'url': BASE + '/lv/electronics/tvs/led/sell/',
        'enabled': False,
        'filters': {
            'Cena': {'max': 300},
            'Diagonāle': {'min': 50},               # inches
            'Stāv.': {'equals': 'jaun.'},
        },
        'show': ['Marka', 'Modelis', 'Diagonāle', 'Stāv.', 'Cena'],
        'max_pages': 10,
    },
    {
        'name': 'Flats, not top floor',
        'url': BASE + '/lv/real-estate/flats/riga/centre/sell/',
        'enabled': False,
        'filters': {
            'Ist.': {'min': 3},
            # 'Stāvs' is floor/total, so "not the top floor" needs both numbers.
            'where': lambda row: (
                len(row['columns']['stavs'].split('/')) == 2
                and all(p.strip().isdigit() for p in row['columns']['stavs'].split('/'))
                and int(row['columns']['stavs'].split('/')[0])
                < int(row['columns']['stavs'].split('/')[1])
            ),
        },
        'show': ['Iela', 'Ist.', 'm2', 'Stavs', 'Cena'],
        'max_pages': 20,
    },
]
