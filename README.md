# AutoDice

Automatically applies to **Easy Apply** jobs on [Dice.com](https://www.dice.com) using Playwright browser automation.

- Searches multiple job titles in one run
- Skips jobs already applied to (Dice detects this natively)
- Deduplicates links within a session so the same posting isn't hit twice
- Handles single-page and two-page application flows

---

## Requirements

- Python 3.10+
- A Dice.com account

---

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/your-username/AutoDice.git
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

`config.py` is git-ignored — your credentials will never be committed.

---

## Usage

```bash
python DiceC.py
```

A visible Chrome window will open so you can monitor the bot. It will:

1. Log in to Dice.com
2. Search each role in `JOB_TITLES` with the **Easy Apply** filter active
3. Open every listing and click **Easy Apply**
4. Submit the application (advancing past review pages if needed)
5. Skip any jobs already applied to

---

## Notes

- **Easy Apply only** — the bot skips any listing that requires an external application.
- **No screening questions** — jobs with required screening questions will be skipped at the submit step. Apply to those manually.
- The browser runs in headed (visible) mode intentionally so you can intervene if needed.

---

## Disclaimer

Use responsibly and in accordance with [Dice.com's Terms of Service](https://www.dice.com/legal/terms-of-use). This tool is for personal job search automation only.
