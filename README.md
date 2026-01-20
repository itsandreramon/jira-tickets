# Jira Ticket Scraper

Scrapes Jira tickets assigned to you from jira.tools.sap and saves each ticket description to a separate text file.

## Setup

1. Create a Python virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install playwright
playwright install chromium
```

2. Create a `.jira_credentials.json` file with your SAP credentials:

```json
{"username": "your.email@sap.com", "password": "your-password"}
```

## Usage

```bash
./scrape-jira.sh                          # Fetch all tickets assigned to you
./scrape-jira.sh --status "In Progress"   # Fetch only in-progress tickets
./scrape-jira.sh --status "Open"          # Fetch only open tickets
./scrape-jira.sh --login                  # Force new login (refresh session)
./scrape-jira.sh --help                   # Show help with all options
```

### Common Status Values

- `Open`
- `In Progress`
- `Ready for Review`
- `In Review`
- `Ready to Submit`
- `Done`
- `Closed`

Note: Status values are case-sensitive and may vary by project.

## Output

Output files are saved to the `output/` directory, one `.txt` file per ticket.

## Files

- `jira_scraper.py` - Main Python scraper using Playwright
- `scrape-jira.sh` - Shell wrapper script
- `.jira_credentials.json` - Your SAP credentials (not tracked in git)
- `.jira_cookies.json` - Saved session cookies (not tracked in git)
- `output/` - Ticket description files (not tracked in git)
