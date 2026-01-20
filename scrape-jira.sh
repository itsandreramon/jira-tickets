#!/bin/bash
#
# Jira Ticket Scraper
# Scrapes tickets assigned to you from jira.tools.sap
#
# Usage:
#   ./scrape-jira.sh                          # Fetch all tickets
#   ./scrape-jira.sh --status "In Progress"   # Fetch only in-progress tickets
#   ./scrape-jira.sh --login                  # Force new login
#   ./scrape-jira.sh --help                   # Show help
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_SCRIPT="$SCRIPT_DIR/jira_scraper.py"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at $VENV_DIR"
    echo "Please run:"
    echo "  cd $SCRIPT_DIR"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install playwright"
    echo "  playwright install chromium"
    exit 1
fi

# Pass all arguments directly to Python script
"$VENV_DIR/bin/python" "$PYTHON_SCRIPT" "$@"

if [ $? -eq 0 ]; then
    echo ""
    echo "Output files are in: $SCRIPT_DIR/output/"
fi
