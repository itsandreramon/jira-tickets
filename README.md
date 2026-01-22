# Jira Ticket Scraper

Scrapes Jira tickets assigned to you and saves each ticket description to a separate text file.

Also supports **changing ticket status** via the Jira transitions API.

## Setup

1. Create a Python virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install playwright
playwright install chromium
```

2. Create a `.env` file with your Jira configuration:

```bash
JIRA_BASE_URL=https://jira.example.com
JIRA_BOARD_ID=12345  # Optional: Agile board ID for sprint operations
```

3. Create a `.jira_credentials.json` file with your credentials:

```json
{"username": "your.email@example.com", "password": "your-password"}
```

## Usage

### Fetching Tickets

```bash
./scrape-jira.sh                          # Fetch all tickets assigned to you
./scrape-jira.sh --status "In Progress"   # Fetch only in-progress tickets
./scrape-jira.sh --status "Open"          # Fetch only open tickets
./scrape-jira.sh --login                  # Force new login (refresh session)
./scrape-jira.sh --help                   # Show help with all options
```

### Changing Ticket Status

```bash
./scrape-jira.sh --change-status TICKET-123 --to-status "In Progress"
./scrape-jira.sh -c TICKET-123 -t "Done"
```

The script will:
1. Fetch available transitions for the ticket
2. Find the transition that leads to the target status
3. Execute the transition

Note: Available transitions depend on the ticket's current status and your project's workflow.

### Common Status Values

- `Open`
- `In Progress`
- `Ready for Review`
- `In Review`
- `Done`
- `Closed`

Note: Status values are case-sensitive and may vary by project.

## Output

Tickets are organized into folders by their Jira status:

```
output/
├── blocked/
├── code_review/
├── completed/
├── in_progress/
├── ready_for_testing/
└── testing/
```

Each ticket is saved as a `.txt` file in its corresponding status folder.

## Files

- `jira_scraper.py` - Main Python scraper using Playwright
- `scrape-jira.sh` - Shell wrapper script
- `.env` - Environment configuration (not tracked in git)
- `.jira_credentials.json` - Your credentials (not tracked in git)
- `.jira_cookies.json` - Saved session cookies (not tracked in git)
- `output/` - Ticket description files (not tracked in git)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_BASE_URL` | Yes | Base URL of your Jira instance |
| `JIRA_BOARD_ID` | No | Agile board ID for sprint operations |
