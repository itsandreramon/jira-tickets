#!/bin/bash
#
# Jira Ticket Scraper
# Scrapes in-progress tickets assigned to you from jira.tools.sap
#
# Usage:
#   ./scrape-jira.sh          # Run with saved session
#   ./scrape-jira.sh --login  # Force new login
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

# Parse arguments
ARGS=""
for arg in "$@"; do
    case $arg in
        --login)
            ARGS="$ARGS --login"
            ;;
        *)
            ARGS="$ARGS $arg"
            ;;
    esac
done

# Run the scraper
"$VENV_DIR/bin/python" "$PYTHON_SCRIPT" $ARGS

echo ""
echo "Output files are in: $SCRIPT_DIR/output/"
