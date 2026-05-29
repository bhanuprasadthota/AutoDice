# AutoDice

> Automate your Dice.com Easy Apply job search — so you can focus on interviews, not clicking.

AutoDice is a Playwright-based Python bot that logs into your Dice.com account, searches across multiple job titles, and automatically submits Easy Apply applications — while keeping a full CSV log of every result.

---

## Demo

<!-- Add a demo GIF or screenshot here once you have one.

     How to record a GIF on macOS:
       - Gifox (gifox.io) — lightweight menu bar recorder, exports GIF directly
       - LICEcap (github.com/nicowillis/licecap) — free, drag to select region
       - Built-in: record with QuickTime → convert with ffmpeg:
           ffmpeg -i demo.mov -vf "fps=10,scale=800:-1" demo.gif

     Suggested clip (30–60 s):
       1. Bot launches, Chrome opens
       2. Dice.com login happens automatically
       3. Search results load with Easy Apply filter
       4. Two or three job listings open and get submitted
       5. Terminal shows "submitted" lines and CSV written

     Once you have the file, drop it into the repo root and replace this
     comment block with:

       ![AutoDice demo](demo.gif)

     Or for a static screenshot:

       ![AutoDice screenshot](screenshot.png)
-->

> **Recording tip:** run with `AUTODICE_MAX_APPLICATIONS=3 AUTODICE_DRY_RUN=1 python DiceC.py` to get a clean, short clip without submitting real applications.

---

## What it does

```
Login → Search → Collect links → Filter already-applied → Apply → Log result
```

For each configured job title, AutoDice:

1. Logs into Dice.com (auto or manual fallback)
2. Searches with the Easy Apply filter pre-enabled
3. Paginates through all result pages and caches links to CSV
4. Skips any job already visited in a previous run
5. Opens each listing, detects the apply button, and submits the application
6. Handles multi-step wizards (Next → Review → Submit)
7. Records every outcome — `submitted`, `already_applied`, `stuck`, etc.

---

## Features

- **Persistent logs** — CSV-backed history means zero duplicate applications across sessions
- **Link caching** — scraped links are saved so re-runs skip the search phase entirely
- **Smart apply flow** — handles Dice's multi-step wizard: Next, Review, Submit
- **Auto login recovery** — re-authenticates mid-run if Dice redirects to sign-in
- **Manual login fallback** — pauses and waits up to 5 minutes if automated login fails
- **Dry-run mode** — walks the flow without submitting; great for testing
- **Debug screenshots** — captures the browser state when a submission gets stuck
- **Log rotation** — automatically archives `applications.csv` when it hits a size limit
- **Configurable via env vars** — tweak limits, roles, and directories per run without editing code

---

## Requirements

- Python 3.10+
- A Dice.com account with Easy Apply-eligible jobs in your search

---

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/bhanuprasadthota/AutoDice.git
cd AutoDice
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

**3. Configure your credentials and roles**

```bash
cp config.example.py config.py
```

Edit `config.py`:

```python
DICE_EMAIL    = "you@example.com"
DICE_PASSWORD = "yourpassword"
LOCATION      = "USA"               # or "Remote", "New York", etc.
JOB_TITLES    = [
    "Machine Learning Engineer",
    "Data Scientist",
    "MLOps Engineer",
    # add or remove any titles
]
```

`config.py` is git-ignored — your credentials will never be committed.

---

## Usage

```bash
python DiceC.py
```

A visible Chrome window opens so you can monitor progress. The bot logs each step to the terminal and writes results to `autodice-logs/`.

---

## Runtime options

Override any setting with environment variables — no code changes needed:

| Variable | Default | Description |
|---|---|---|
| `AUTODICE_MAX_APPLICATIONS` | `0` (unlimited) | Stop after N visited jobs |
| `AUTODICE_MAX_SEARCH_PAGES` | `0` (unlimited) | Limit result pages scraped per role |
| `AUTODICE_JOB_TITLES` | from `config.py` | Comma-separated role override for this run |
| `AUTODICE_DRY_RUN` | `0` | Set to `1` to skip final submission |
| `AUTODICE_STOP_AT_APPLY` | `0` | With dry run: also skip clicking Apply |
| `AUTODICE_MANUAL_LOGIN_TIMEOUT` | `300` | Seconds to wait for manual login; `0` disables |
| `AUTODICE_LOG_DIR` | `autodice-logs` | Output directory for CSVs |
| `AUTODICE_DEBUG_DIR` | `autodice-debug` | Output directory for debug screenshots |
| `AUTODICE_MAX_LOG_BYTES` | `5242880` (5 MB) | Rotate `applications.csv` at this size |

**Examples**

```bash
# Apply to 10 jobs and stop
AUTODICE_MAX_APPLICATIONS=10 python DiceC.py

# Override roles for this run only
AUTODICE_JOB_TITLES="SAP ABAP Developer,Salesforce Developer" python DiceC.py

# Dry run — navigate the flow but don't submit
AUTODICE_DRY_RUN=1 AUTODICE_MAX_APPLICATIONS=5 python DiceC.py
```

---

## Output files

All runtime files are written under `autodice-logs/` (configurable):

| File | Contents |
|---|---|
| `applications.csv` | One row per visited job: timestamp, role, URL, title, status, message |
| `job_queue.csv` | Cached job links by role — reused on future runs to skip re-scraping |

**Status values in `applications.csv`**

| Status | Meaning |
|---|---|
| `submitted` | Application successfully submitted |
| `already_applied` | Dice showed "already applied" on load |
| `no_easy_apply` | No Easy Apply button found on the listing |
| `stuck` | Multi-step wizard didn't reach Submit; debug screenshot saved |
| `dry_run_easy_apply_ready` | Dry run: Apply button found, not clicked |
| `dry_run_ready_to_submit` | Dry run: Submit button reached, not clicked |
| `load_failed` | Page failed to load |

---

## Project structure

```
AutoDice/
├── DiceC.py            # Main bot
├── config.py           # Your credentials and job titles (git-ignored)
├── config.example.py   # Template to copy from
├── requirements.txt
├── autodice-logs/      # Generated: CSV logs and link cache
└── autodice-debug/     # Generated: screenshots of stuck applications
```

---

## Notes

- **Easy Apply only** — listings that redirect to an external site are skipped automatically.
- **Multi-step wizards** — the bot clicks Next/Continue/Review up to four times before giving up and logging `stuck`.
- **Stuck jobs** — if a listing requires answers to custom questions, it will be marked `stuck`; review the debug screenshot and apply manually.
- The browser runs in **headed mode** intentionally so you can intervene or monitor at any time.

---

## Disclaimer

Use responsibly and in accordance with [Dice.com's Terms of Service](https://www.dice.com/legal/terms-of-use). This tool is intended for personal job search automation only.
