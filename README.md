# ssbot — ss.lv listing watcher

Polls ss.lv search results and Telegrams you **newly appeared** listings. Works with any
ss.lv results page — cars, flats, TVs, land — because columns are read from the page's own
header row rather than hardcoded.

## Setup

```bash
./install.sh                 # creates ./.venv, installs deps
cp .env.example .env         # then fill in your token and chat id
```

```ini
TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=-1001234567890
```

Token comes from [@BotFather](https://t.me/BotFather). For the chat id: add the bot to the
group, send a message, run `python test2.py`. Group ids are negative.

Real env vars override `.env`, so `TELEGRAM_CHAT_ID=480979058 python parser.py` tests
against your private chat without editing anything.

> **Rotate your token** — the original was committed and pasted into a chat. @BotFather →
> `/revoke`, then update `.env`.

## Run

```bash
python parser.py --dry-run   # show matches; send nothing, save nothing
python parser.py             # first run records a baseline silently, then notifies
```

| Flag | Effect |
|---|---|
| `--dry-run` | Print matches only. Use while tuning filters. |
| `--notify-all` | Send every match, ignoring state. |
| `--search NAME` | Run only the named search. Repeatable. |
| `--columns URL` | List a page's filterable columns and exit. |

The first real run **sends nothing** — it records what already exists so you don't get
dozens of messages at once. Delete `seen_listings.json` to re-baseline.

## Filters

Easiest way — the wizard reads the page, shows real values, previews matches, and prints a
pasteable config:

```bash
python wizard.py https://www.ss.com/lv/transport/cars/bmw/x3/sell/
```

```
  Column: Tilpums   (text, 7 distinct values)
    values: 2.0D (128), 3.0D (120), 2.0 (15), 2.0H (9), 3.0 (8), E (5), 2.5 (2)
    1) Any  2) Dīzelis  3) Benzīns  4) Hibrīds  5) Elektriskais  6) Exact value
  Dzinējs / fuel type? [1]: 2

10 of 287 listings match.
```

Or write them by hand in [searches.py](searches.py) — the only file you normally edit.
Filter keys are the page's own column names, matched case- and accent-insensitively
(`m²` = `m2`, `Stāvs` = `Stavs`):

```python
{
    'name': 'BMW X3',
    'url': BASE + '/lv/transport/cars/bmw/x3/sell/',
    'filters': {
        'Gads': {'min': 2018},
        'Tilpums': {'contains': 'D'},      # diesel
        'Cena': {'max': 35000},
    },
    'show': ['Gads', 'Tilpums', 'Nobraukums', 'Cena'],
    'max_pages': 20,
},
```

| Operator | Example |
|---|---|
| `min` / `max` | `{'min': 2018}`, `{'max': 35000}` |
| `contains` / `not_contains` | `{'contains': '2.0D'}` |
| `equals` | `{'equals': 'Renov.'}` |
| `where` | `lambda row: ...` — see below |

`min`/`max` read the **first number** in the cell: `23,950 €` → 23950, `133 tūkst.` → 133,
`4/5` → 4. Cells with no number never match a `min`/`max`.

`SEARCHES` is a list — add as many as you like. `'enabled': False` parks one; the file ships
with parked examples for flats, LED TVs and a `where` filter. State is shared and keyed on
listing id, so nothing is reported twice.

> Why a `.py` file and not JSON or `.env`? `where` filters are lambdas, which only Python
> can hold. Keeping searches in their own module means `parser.py` stays untouched.

### Fuel type (Dzinējs)

ss.lv's **Dzinējs** dropdown is POST-only with no bookmarkable URL, and the results table
has no engine column. Fuel is the suffix on `Tilpums`:

| Want | Rule |
|---|---|
| Dīzelis | `{'contains': 'D'}` → `2.0D`, `3.0D` |
| Hibrīds | `{'contains': 'H'}` → `2.0H` |
| Elektriskais | `{'equals': 'E'}` |
| Benzīns | `'where': lambda row: row['columns']['tilpums'][-1:].isdigit()` |

Petrol needs `where` because `not_contains: 'D'` would also let hybrids and electrics
through.

### Other categories

Any leaf results page works unchanged — TVs give `Marka, Modelis, Diagonāle, Stāv., Cena`;
flats give `Iela, Ist., m², Stāvs, Sērija, Cena`.

Category **chooser** pages have no listing table and fail with
`No header row found — is that a results page?`. Drill down until the table appears:
`/electronics/tvs/` fails, `/electronics/tvs/led/` works.

## Schedule it

```bash
./schedule.sh install        # every 15 min via launchd; also: status, logs, uninstall
```

Interval must divide 60 (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60). Logs to
`~/Library/Logs/ssbot.log`, timestamped, with failures marked and a non-zero exit code.

**Nothing runs while the Mac is asleep**, but the job uses `StartCalendarInterval`, so
launchd fires it once on wake with all missed runs coalesced — unlike cron, which drops
them silently. That's the main reason for launchd over crontab here.

> **If the project itself lived under `~/Desktop`, `~/Documents` or `~/Downloads`**, launchd
> would fail every unattended run with `posix_spawn error 0x1 / exit 78`, even though
> running the exact same command by hand works fine. The cause: `xpcproxy` (launchd's spawn
> helper) is sandboxed out of those folders, and — unlike a normal app — it can never be
> granted Full Disk Access to get back in. That's why the log above lives in
> `~/Library/Logs/` rather than next to the project: it's the one thing that must be off
> Desktop for the job to spawn at all. Full Disk Access on the Python interpreter is still
> worth having — it's what lets the running script read `.env`/`searches.py` and write
> `seen_listings.json` once it's actually started — it just can't rescue that pre-exec step.

For true always-on you need a machine that stays awake. Note **cloud schedulers won't
work**: ss.com drops traffic from datacenter IPs, so Apps Script, GitHub Actions and most
VPS hosts get `Address unavailable`.

## Gotchas

- **Use a deal-type URL.** `/real-estate/flats/riga/centre/` mixes sales (`215,000 €`) with
  rentals (`850 €/mēn.`), and `max: 250000` matches both. Use `/sell/`, `/hand_over/` (rent)
  or `/buy/`.
- **`Nobraukums` is in thousands** — `{'max': 150}` means 150 000 km.
- **Don't install the `telegram` package.** The PyPI package of that name is an unrelated
  stub, and it's what caused `ImportError: cannot import name 'Bot'`. This bot calls the
  Telegram HTTP API directly; no library needed.
- Credentials are checked only when sending, so `--dry-run`, `--columns` and `wizard.py`
  work with no `.env`.

## Files

| File | Purpose |
|---|---|
| [searches.py](searches.py) | **Your searches.** The only file you normally edit. |
| [wizard.py](wizard.py) | Interactive filter builder. |
| [parser.py](parser.py) | The watcher itself — no editing needed. |
| [config.py](config.py) | Loads `.env`; defines `BASE`. |
| [schedule.sh](schedule.sh) | launchd install / status / logs / uninstall. |
| [install.sh](install.sh) | Creates `./.venv`. |
| [test.py](test.py) / [test2.py](test2.py) | Send a test message / find a chat id. |

Git-ignored: `.env`, `.venv/`, `seen_listings.json`, `ssbot.log`.

## Optional settings

Add to `.env` only to change a default: `SSBOT_STATE_FILE`, `SSBOT_REQUEST_TIMEOUT` (30),
`SSBOT_PAGE_DELAY` (1.0), `SSBOT_MESSAGE_DELAY` (0.5), `SSBOT_USER_AGENT`.
