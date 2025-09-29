import json
from datetime import datetime, timezone
from mcp.server import Server
from mcp.server.stdio import stdio_server

from death_scraper import run_scrape_interactive
 # reuse your scraper

server = Server("death-scraper")

@server.tool()
def scrape_daily():
    """
    Run the daily death-case scraper (today's data).
    Always returns a JSON array of at least 15 cases.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    print(f"[MCP] Running scraper for {today}...")

    # run scraper (you may modify run_scrape_interactive to return data instead of saving only)
    run_scrape_interactive()

    # load the JSON file that scraper wrote
    with open("scrap_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    return data[-15:]  # return last 15 records for context

if __name__ == "__main__":
    stdio_server(server).run()
