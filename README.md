# AutoDice

AutoDice is a Playwright-based automation tool for applying to Dice.com Easy Apply jobs from a configured Dice account.

- Searches one or more configured job titles.
- Uses Dice's Easy Apply filter.
- Caches extracted job links in CSV so future runs do not re-scrape the same searches.
- Logs every visited job and result status to CSV.
- Skips links already processed in previous runs.
- Supports bounded runs for safer testing.
- Handles Dice's current two-step application wizard.

---

## Requirements

- Python 3.10+
- A Dice.com account

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

**3. Configure your details**

```bash
cp config.example.py config.py
```

Open `config.py` and fill in:

| Field | Description |
|---|---|
| `DICE_EMAIL` | Your Dice.com login email |
| `DICE_PASSWORD` | Your Dice.com password |
| `JOB_TITLES` | List of roles to search for |
| `LOCATION` | Search location (e.g. `"USA"`, `"Remote"`) |

`config.py` is git-ignored, so your credentials will never be committed.

---

## Usage

```bash
python DiceC.py
```

A visible Chrome window will open so you can monitor the bot. It will:

1. Log in to Dice.com
2. Load cached links for each role when available
3. Search Dice only when a role has no cached links yet
4. Open each unprocessed listing
5. Submit Easy Apply applications
6. Record the result in `autodice-logs/applications.csv`

---

## Runtime Options

Use environment variables to control each run:

| Variable | Description |
|---|---|
| `AUTODICE_MAX_APPLICATIONS` | Stop after this many visited jobs. `0` means no limit. |
| `AUTODICE_MAX_SEARCH_PAGES` | Limit how many result pages are scraped per new role. `0` means no limit. |
| `AUTODICE_JOB_TITLES` | Comma-separated role override for a single run. |
| `AUTODICE_DRY_RUN` | Set to `1` to stop before final submission. |
| `AUTODICE_STOP_AT_APPLY` | With dry run enabled, stop before clicking Easy Apply. |
| `AUTODICE_MANUAL_LOGIN_TIMEOUT` | Seconds to wait for manual login if Dice redirects to sign-in. Default is `300`; set `0` to disable. |
| `AUTODICE_LOG_DIR` | Directory for CSV logs and cached job links. |
| `AUTODICE_MAX_LOG_BYTES` | Rotate `applications.csv` after this size in bytes. |

Examples:

```bash
AUTODICE_MAX_APPLICATIONS=10 python DiceC.py
```

```bash
AUTODICE_JOB_TITLES="SAP ABAP Developer,Salesforce Developer" AUTODICE_MAX_SEARCH_PAGES=1 python DiceC.py
```

```bash
AUTODICE_DRY_RUN=1 AUTODICE_MAX_APPLICATIONS=5 python DiceC.py
```

---

## Output Files

AutoDice writes runtime files under `autodice-logs/`:

| File | Purpose |
|---|---|
| `applications.csv` | One row per visited job with status and message. |
| `job_queue.csv` | Cached Dice job links by role. |

If `applications.csv` reaches `AUTODICE_MAX_LOG_BYTES`, it is rotated with a timestamp and a fresh file is created.

---

## Notes

- **Easy Apply only**: the bot skips any listing that requires an external application.
- Jobs with required custom questions may be marked as `stuck` and should be reviewed manually.
- The browser runs in headed (visible) mode intentionally so you can intervene if needed.

---

## Disclaimer

Use responsibly and in accordance with [Dice.com's Terms of Service](https://www.dice.com/legal/terms-of-use). This tool is for personal job search automation only.
