#!/usr/bin/env python3
"""
Jira Ticket Scraper

Fetches tickets from jira.tools.sap using Playwright and the Jira REST API.
Saves each ticket description to a separate text file in the output directory.

Also supports changing ticket status via the Jira transitions API.

Examples:
    ./scrape-jira.sh                        # Fetch all tickets assigned to you
    ./scrape-jira.sh --status "In Progress" # Fetch only in-progress tickets
    ./scrape-jira.sh --status "Open"        # Fetch only open tickets
    ./scrape-jira.sh --login                # Force new login
    ./scrape-jira.sh --change-status TICKET-123 --to-status "In Progress"
"""
import asyncio
import argparse
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

# =============================================================================
# Configuration - paths relative to script location for portability
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
COOKIES_FILE = SCRIPT_DIR / ".jira_cookies.json"
CREDENTIALS_FILE = SCRIPT_DIR / ".jira_credentials.json"
OUTPUT_DIR = SCRIPT_DIR / "output"

JIRA_BASE_URL = "https://jira.tools.sap"

# Common Jira status values for reference
VALID_STATUSES = [
    "Open",
    "In Progress",
    "Ready for Review",
    "In Review",
    "Ready to Submit",
    "Done",
    "Closed",
]

# =============================================================================
# Cookie and credential management
# =============================================================================


async def load_cookies():
    """Load saved session cookies from file."""
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE, "r") as f:
            return json.load(f)
    return []


async def save_cookies(cookies):
    """Save session cookies to file for reuse."""
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)


async def load_credentials():
    """Load user credentials from file."""
    if CREDENTIALS_FILE.exists():
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    return None

# =============================================================================
# Authentication
# =============================================================================


async def login(page):
    """
    Handle Microsoft SSO login flow.
    
    SAP Jira uses Microsoft Azure AD for authentication. This function
    fills in the email and password forms automatically.
    """
    credentials = await load_credentials()
    if not credentials:
        print("No credentials found. Please create .jira_credentials.json")
        return False
    
    print("Logging in to Jira...")
    await page.goto(f"{JIRA_BASE_URL}/login.jsp")
    await page.wait_for_timeout(2000)
    
    # Check if redirected to Microsoft login
    if "login.microsoftonline.com" in page.url:
        # Enter email
        await page.fill('input[type="email"]', credentials["username"])
        await page.click('input[type="submit"]')
        await page.wait_for_timeout(2000)
        
        # Enter password (may fail if already authenticated via SSO)
        try:
            await page.fill('input[type="password"]', credentials["password"])
            await page.click('input[type="submit"]')
        except:
            pass
        
        # Wait for redirect back to Jira
        await page.wait_for_timeout(5000)
    
    return True

# =============================================================================
# Jira API interaction
# =============================================================================


async def get_transitions(page, issue_key):
    """
    Fetch available transitions for a ticket.
    
    Jira uses workflow transitions to change status. This function
    returns the list of available transitions for the given issue.
    
    Args:
        page: Playwright page object with active session
        issue_key: Jira issue key (e.g., "PROJECT-123")
    
    Returns:
        List of transitions with id and name, or None on failure
    """
    api_url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/transitions"
    
    print(f"Fetching available transitions for {issue_key}...")
    response = await page.goto(api_url)
    
    if response.status != 200:
        print(f"Failed to fetch transitions: HTTP {response.status}")
        return None
    
    # Extract JSON from page content
    content = await page.content()
    
    # Try to find JSON in <pre> tags first (Chrome format)
    json_match = re.search(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL)
    if json_match:
        json_text = json_match.group(1)
        json_text = json_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    else:
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
        if body_match:
            json_text = body_match.group(1).strip()
            json_text = re.sub(r'<[^>]+>', '', json_text)
            json_text = json_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
        else:
            json_text = content
    
    try:
        data = json.loads(json_text)
        return data.get("transitions", [])
    except json.JSONDecodeError as e:
        print(f"Failed to parse transitions JSON: {e}")
        return None


def find_transition_by_status(transitions, target_status):
    """
    Find a transition that leads to the target status.
    
    Args:
        transitions: List of transition objects from Jira API
        target_status: Desired status name (case-insensitive)
    
    Returns:
        Transition object if found, None otherwise
    """
    target_lower = target_status.lower()
    for transition in transitions:
        # The transition's "to" field contains the destination status
        to_status = transition.get("to", {}).get("name", "")
        if to_status.lower() == target_lower:
            return transition
    return None


async def execute_transition(page, issue_key, transition_id):
    """
    Execute a transition to change ticket status.
    
    Uses page.evaluate() to make an authenticated POST request
    using the browser's session cookies.
    
    Args:
        page: Playwright page object with active session
        issue_key: Jira issue key (e.g., "PROJECT-123")
        transition_id: ID of the transition to execute
    
    Returns:
        True on success, False on failure
    """
    api_url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/transitions"
    
    print(f"Executing transition {transition_id} on {issue_key}...")
    
    # Use page.evaluate to make POST request with browser cookies
    result = await page.evaluate("""
        async (args) => {
            const [url, transitionId] = args;
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        transition: { id: transitionId }
                    }),
                    credentials: 'include'
                });
                return {
                    ok: response.ok,
                    status: response.status,
                    statusText: response.statusText
                };
            } catch (error) {
                return { ok: false, error: error.message };
            }
        }
    """, [api_url, transition_id])
    
    if result.get("ok"):
        return True
    else:
        error_msg = result.get("error") or f"HTTP {result.get('status')} {result.get('statusText')}"
        print(f"Failed to execute transition: {error_msg}")
        return False


async def change_ticket_status(page, issue_key, target_status):
    """
    Change a ticket's status to the target status.
    
    This function orchestrates the full status change:
    1. Fetch available transitions for the issue
    2. Find the transition that leads to the target status
    3. Execute the transition
    
    Args:
        page: Playwright page object with active session
        issue_key: Jira issue key (e.g., "PROJECT-123")
        target_status: Desired status name
    
    Returns:
        True on success, False on failure
    """
    # Get available transitions
    transitions = await get_transitions(page, issue_key)
    if transitions is None:
        return False
    
    if not transitions:
        print(f"No transitions available for {issue_key}")
        print("This may mean you don't have permission to change the status,")
        print("or the ticket is in a state where no transitions are allowed.")
        return False
    
    # Show available transitions
    print(f"\nAvailable transitions for {issue_key}:")
    for t in transitions:
        to_status = t.get("to", {}).get("name", "Unknown")
        print(f"  - {t.get('name')} -> {to_status}")
    
    # Find matching transition
    transition = find_transition_by_status(transitions, target_status)
    if not transition:
        print(f"\nError: Cannot transition to '{target_status}'")
        print(f"Available target statuses: {', '.join(t.get('to', {}).get('name', '') for t in transitions)}")
        return False
    
    print(f"\nTransitioning {issue_key} to '{target_status}' via '{transition.get('name')}'...")
    
    # Execute the transition
    success = await execute_transition(page, issue_key, transition.get("id"))
    
    if success:
        print(f"Successfully changed {issue_key} status to '{target_status}'")
    
    return success


def build_jql_query(status=None):
    """
    Build JQL query based on provided filters.
    
    Args:
        status: Optional status filter (e.g., "In Progress", "Open")
    
    Returns:
        JQL query string
    """
    query_parts = ["assignee = currentUser()"]
    
    if status:
        query_parts.append(f"status = '{status}'")
    
    query_parts.append("ORDER BY updated DESC")
    
    return " AND ".join(query_parts[:-1]) + " " + query_parts[-1]


async def fetch_tickets_via_api(page, jql_query, max_results=100):
    """
    Fetch tickets using Jira REST API.
    
    Uses the browser session (with cookies) to authenticate the API request.
    Returns the parsed JSON response or None on failure.
    """
    # URL-encode the JQL query
    jql_encoded = jql_query.replace(" ", "%20").replace("=", "%3D").replace("'", "%27").replace("(", "%28").replace(")", "%29")
    
    # Build API URL with fields we need
    api_url = f"{JIRA_BASE_URL}/rest/api/2/search?jql={jql_encoded}&maxResults={max_results}&fields=key,summary,status,priority,assignee,reporter,labels,created,updated,description"
    
    print(f"Query: {jql_query}")
    print("Fetching tickets from API...")
    response = await page.goto(api_url)
    
    if response.status != 200:
        print(f"API request failed with status {response.status}")
        return None
    
    # Extract JSON from page content
    # The browser wraps JSON responses in HTML, so we need to extract it
    content = await page.content()
    
    # Try to find JSON in <pre> tags first (Chrome format)
    json_match = re.search(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL)
    if json_match:
        json_text = json_match.group(1)
        # Decode HTML entities
        json_text = json_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    else:
        # Fallback: try to extract from body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
        if body_match:
            json_text = body_match.group(1).strip()
            # Strip any remaining HTML tags
            json_text = re.sub(r'<[^>]+>', '', json_text)
            json_text = json_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
        else:
            json_text = content
    
    # Parse and return JSON
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        return None

# =============================================================================
# Ticket processing and output
# =============================================================================


def format_ticket(issue):
    """
    Extract relevant fields from Jira issue response.
    
    Handles missing/null fields gracefully with default values.
    """
    fields = issue.get("fields", {})
    key = issue.get("key", "N/A")
    
    return {
        "key": key,
        "summary": fields.get("summary", "N/A"),
        "status": fields.get("status", {}).get("name", "") if fields.get("status") else "",
        "priority": fields.get("priority", {}).get("name", "N/A") if fields.get("priority") else "N/A",
        "assignee": fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned",
        "reporter": fields.get("reporter", {}).get("displayName", "N/A") if fields.get("reporter") else "N/A",
        "labels": ", ".join(fields.get("labels", [])) or "None",
        "created": fields.get("created", "N/A"),
        "updated": fields.get("updated", "N/A"),
        "description": fields.get("description", "No description provided") or "No description provided",
        "url": f"{JIRA_BASE_URL}/browse/{key}"
    }


def sanitize_folder_name(name):
    """
    Convert status name to a valid folder name.
    
    Replaces spaces and special characters with underscores.
    """
    if not name:
        return "Unknown"
    # Replace spaces and special chars with underscores, convert to lowercase
    sanitized = re.sub(r'[^\w\-]', '_', name.lower())
    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')


def save_ticket_description(ticket):
    """
    Save ticket details to a text file.
    
    Creates one file per ticket, organized into folders by status.
    """
    # Create status-based subfolder
    status_folder = sanitize_folder_name(ticket['status'])
    ticket_dir = OUTPUT_DIR / status_folder
    ticket_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = ticket_dir / f"{ticket['key']}.txt"
    
    content = f"""Ticket: {ticket['key']}
Summary: {ticket['summary']}
URL: {ticket['url']}
Status: {ticket['status']}
Priority: {ticket['priority']}
Assignee: {ticket['assignee']}
Reporter: {ticket['reporter']}
Labels: {ticket['labels']}
Created: {ticket['created']}
Updated: {ticket['updated']}

Description:
{ticket['description']}
"""
    
    with open(filepath, "w") as f:
        f.write(content)
    
    print(f"Saved: {filepath}")
    return filepath

# =============================================================================
# Main entry point
# =============================================================================


async def main():
    """Main entry point - parse args, authenticate, fetch and save tickets."""
    parser = argparse.ArgumentParser(
        description="Scrape Jira tickets assigned to you, or change ticket status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  %(prog)s                        Fetch all tickets assigned to you
  %(prog)s --status "In Progress" Fetch only in-progress tickets
  %(prog)s --status "Open"        Fetch only open tickets
  %(prog)s --login                Force new login (refresh session)
  
  %(prog)s --change-status TICKET-123 --to-status "In Progress"
                                  Change ticket status

Common status values:
  {', '.join(VALID_STATUSES)}

Note: Status values are case-sensitive and may vary by project.
"""
    )
    parser.add_argument(
        "--status", "-s",
        type=str,
        default=None,
        metavar="STATUS",
        help="Filter by ticket status (e.g., 'In Progress', 'Open')"
    )
    parser.add_argument(
        "--login", "-l",
        action="store_true",
        help="Force new login (ignore saved session)"
    )
    parser.add_argument(
        "--change-status", "-c",
        type=str,
        default=None,
        metavar="TICKET_KEY",
        help="Change status of a ticket (requires --to-status)"
    )
    parser.add_argument(
        "--to-status", "-t",
        type=str,
        default=None,
        metavar="STATUS",
        help="Target status for --change-status (e.g., 'In Progress')"
    )
    args = parser.parse_args()
    
    # Validate arguments for status change
    if args.change_status and not args.to_status:
        parser.error("--change-status requires --to-status")
    if args.to_status and not args.change_status:
        parser.error("--to-status requires --change-status")
    
    # Build JQL query based on arguments (only used for fetching)
    jql_query = build_jql_query(status=args.status)
    
    async with async_playwright() as p:
        # Launch headless browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Restore session cookies if available (skip if --login flag)
        if not args.login:
            cookies = await load_cookies()
            if cookies:
                await context.add_cookies(cookies)
        
        page = await context.new_page()
        await page.goto(JIRA_BASE_URL)
        await page.wait_for_timeout(2000)
        
        # Check if we need to login (redirected to login page)
        if "login" in page.url.lower() or "microsoftonline" in page.url:
            print("Session expired or no session found. Logging in...")
            await login(page)
            await page.wait_for_timeout(3000)
        
        # Handle status change mode
        if args.change_status:
            success = await change_ticket_status(page, args.change_status, args.to_status)
            
            # Save cookies for future sessions
            cookies = await context.cookies()
            await save_cookies(cookies)
            
            await browser.close()
            return 0 if success else 1
        
        # Fetch tickets from Jira API
        data = await fetch_tickets_via_api(page, jql_query)
        
        if data and "issues" in data:
            # Save cookies for future sessions
            cookies = await context.cookies()
            await save_cookies(cookies)
            
            # Process and save each ticket
            tickets = [format_ticket(issue) for issue in data["issues"]]
            print(f"\nFound {len(tickets)} tickets")
            
            for ticket in tickets:
                save_ticket_description(ticket)
        else:
            print("Failed to fetch tickets")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
