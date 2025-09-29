#!/usr/bin/env python3
"""
Robust daily death-case scraper (Google News RSS) with detailed terminal logs & progress.
- Interactive: asks for target date (press Enter for today).
- Attempts multiple queries and up to MAX_LINKS_PER_QUERY links each.
- Verbose logging: prints RSS counts, per-link fetch status, reasons for skipping.
- Stops when it has at least MIN_CASES_PER_RUN new records or when limits reached.
- Saves results to scrap_data.json

Run:
  python death_scraper_verbose.py
"""

import re
import json
import time
import argparse
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, unquote, parse_qs

import requests
from bs4 import BeautifulSoup
import feedparser
from dateutil import parser as dtparser

# -------------------------
# Configurable parameters
# -------------------------
OUTPUT_FILE = "scrap_data.json"
MIN_CASES_PER_RUN = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

# Queries used (fallback). We restrict to India using site:in and "when:1d" in RSS fetch.
SEARCH_QUERIES = [
    '("death" OR "dead" OR "dies" OR "body found" OR "victim") site:in',
    '("accident" OR "road accident" OR "road crash") site:in',
    '("murder" OR "killed") site:in',
    '("suicide") site:in',
    '("drowned" OR "drowning") site:in',
]

# mapping domain -> short source code for IDs
DOMAIN_SOURCE_MAP = {
    'timesofindia.indiatimes.com': 'TOI',
    'indianexpress.com': 'IE',
    'ndtv.com': 'NDTV',
    'thehindu.com': 'THEHINDU',
    'hindustantimes.com': 'HT',
    'telegraphindia.com': 'TELEGRAPH',
    'news18.com': 'NEWS18',
}

# How many links to request per query (max)
MAX_LINKS_PER_QUERY = 200

# Politeness / speed
REQUEST_TIMEOUT = 10           # seconds per article fetch
DELAY_BETWEEN_REQUESTS = 0.20  # seconds (reduced to speed up)
MAX_TOTAL_LINKS_TO_TRY = 1000  # safety cap across queries
LOG_EVERY_N = 10               # progress log frequency while processing links

# -------------------------
# Helpers
# -------------------------
def parse_iso_date(dt):
    if not dt:
        return None
    try:
        if isinstance(dt, str):
            return dtparser.parse(dt).date().isoformat()
        # feedparser may present time tuple -> try generic parse
        return dtparser.parse(str(dt)).date().isoformat()
    except Exception:
        return None

def resolve_google_link(link):
    """Resolve Google News wrapper links to original URL when possible."""
    if not link:
        return link
    try:
        parsed = urlparse(link)
        if "news.google" in parsed.netloc and parsed.query:
            q = parse_qs(parsed.query).get("url")
            if q:
                return unquote(q[0])
        # Some RSS items may embed the full original link already
    except Exception:
        pass
    # fallback: return as-is
    return link

def google_news_rss_links(query, max_items=200):
    """Fetch Google News RSS for a query and return resolved links (up to max_items)."""
    q = quote_plus(query + " when:1d")
    rss_url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    print(f"\n[RSS] Fetching RSS for query: {query}")
    print(f"[RSS] URL: {rss_url}")
    feed = feedparser.parse(rss_url)
    n = len(feed.entries)
    print(f"[RSS] feed returned {n} entries (will take up to {max_items})")
    links = []
    for i, entry in enumerate(feed.entries[:max_items], start=1):
        raw_link = entry.get("link")
        resolved = resolve_google_link(raw_link)
        if resolved:
            links.append((resolved, parse_iso_date(getattr(entry, "published", None) or getattr(entry, "published_parsed", None))))
    print(f"[RSS] resolved {len(links)} links from this query")
    return links

def fetch_article_text(url):
    """Fetch article title, text, and meta publish date. Returns (title, text, publish_date_iso)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return None, None, None, f"request-failed:{e}"
    if resp.status_code != 200:
        return None, None, None, f"status-{resp.status_code}"
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        title = (soup.title.string.strip() if soup.title and soup.title.string else "") or ""
        # gather paragraph text
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraphs = [p for p in paragraphs if len(p) > 30]
        text = " ".join(paragraphs[:8]) if paragraphs else ""
        publish_date = None
        for meta_name in ['article:published_time', 'pubdate', 'date', 'dc.date.issued', 'publishdate', 'timestamp']:
            tag = soup.find("meta", attrs={"property": meta_name}) or soup.find("meta", attrs={"name": meta_name})
            if tag and tag.get("content"):
                publish_date = parse_iso_date(tag.get("content"))
                if publish_date:
                    break
        return title, text, publish_date, "ok"
    except Exception as e:
        return None, None, None, f"parse-error:{e}"

def find_age_gender(text):
    age = None; gender = "Unknown"
    m = re.search(r'\baged?\s*(\d{1,3})\b', text, flags=re.I) or re.search(r'(\d{1,3})[-\s]?year[-\s]?old', text, flags=re.I) or re.search(r'(\d{1,3})\s*years?\s*old', text, flags=re.I)
    if m:
        try:
            age = int(m.group(1))
        except Exception:
            age = None
    if re.search(r'\b(man|male|him|he|boy)\b', text, flags=re.I):
        gender = "Male"
    if re.search(r'\b(woman|female|she|her|girl)\b', text, flags=re.I):
        gender = "Female"
    return age, gender

def find_cause_and_context(text):
    t = (text or "").lower()
    if "accident" in t or "crash" in t: return "accident", text[:300]
    if "suicide" in t: return "suicide", text[:300]
    if "murder" in t or "killed" in t: return "homicide", text[:300]
    if "drown" in t: return "drowning", text[:300]
    if "train" in t and ("hit" in t or "collision" in t): return "train collision", text[:300]
    if "shot" in t or "gunshot" in t: return "gunshot", text[:300]
    if "found dead" in t or "body found" in t: return "found dead", text[:300]
    # fallback: pick first 200 chars
    return "death", (text or "")[:300] or None

def domain_to_source(domain):
    return DOMAIN_SOURCE_MAP.get(domain, domain.upper().split(".")[0])

def normalize_case_id(source_code, date_iso, seq):
    return f"{source_code}-{date_iso}-{seq:03d}"

def load_existing_output(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# -------------------------
# Main scraping routine
# -------------------------
def run_scrape_interactive():
    # Interactive date input (Enter => today)
    inp = input("Enter the target date (YYYY-MM-DD) or press Enter for today: ").strip()
    if inp:
        try:
            target_date = dtparser.parse(inp).date().isoformat()
        except Exception:
            print("[ERROR] Invalid date format. Use YYYY-MM-DD")
            return
    else:
        target_date = datetime.now(timezone.utc).date().isoformat()

    print(f"[RUN] Target date: {target_date}")
    existing = load_existing_output(OUTPUT_FILE)
    seen_urls = {e.get("source_url") for e in existing if isinstance(e, dict) and e.get("source_url")}
    print(f"[INFO] Already have {len(existing)} records in {OUTPUT_FILE}. Seen URLs={len(seen_urls)}")

    collected = []
    seq_counters = {}
    total_links_tried = 0

    # iterate queries (fallback list)
    for q_idx, query in enumerate(SEARCH_QUERIES, start=1):
        if len(collected) >= MIN_CASES_PER_RUN:
            break
        print(f"\n[STEP] Running query #{q_idx}/{len(SEARCH_QUERIES)}: {query}")
        try:
            links_with_dates = google_news_rss_links(query, max_items=MAX_LINKS_PER_QUERY)
        except Exception as e:
            print(f"[RSS ERROR] Query failed: {e}")
            continue

        print(f"[STEP] Processing up to {len(links_with_dates)} links from this query.")
        for i, (url, entry_date) in enumerate(links_with_dates, start=1):
            if len(collected) >= MIN_CASES_PER_RUN:
                break
            total_links_tried += 1
            if total_links_tried > MAX_TOTAL_LINKS_TO_TRY:
                print("[LIMIT] Reached overall max links tried cap. Stopping.")
                break

            if not url:
                continue
            if url in seen_urls:
                if i % LOG_EVERY_N == 0:
                    print(f"[SKIP] (already seen) {i}/{len(links_with_dates)} - {url}")
                continue

            # If the RSS entry reports a date and it doesn't match target, skip early
            if entry_date and entry_date != target_date:
                if i % LOG_EVERY_N == 0:
                    print(f"[SKIP] (rss-date-mismatch) {i}/{len(links_with_dates)} - entry_date={entry_date}")
                continue

            if i % LOG_EVERY_N == 1:
                print(f"[INFO] Processing link {i}/{len(links_with_dates)}: {url}")

            title, text, publish_date, fetch_status = fetch_article_text(url)
            if fetch_status != "ok":
                print(f"[FETCH] {i}/{len(links_with_dates)} -> {fetch_status} for {url}")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue

            # when user asked for specific date, ensure article publish_date matches target (best-effort)
            if target_date and publish_date and publish_date != target_date:
                print(f"[SKIP] (article-date-mismatch) publish_date={publish_date} != target={target_date} | {url}")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue
            # if no publish_date and user requested specific date, skip (to avoid wrong-day picks)
            if target_date and not publish_date and entry_date is None:
                # skip ambiguous ones to be conservative
                if i % LOG_EVERY_N == 0:
                    print(f"[SKIP] (no-date-info) skipping ambiguous article {url}")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue

            combined = (title or "") + " " + (text or "")
            # relaxed keyword filter (catch many variants)
            if not re.search(r'\b(dead|death|died|dies|killed|murder|suicide|accident|body found|found dead|victim|drowned|shot)\b', combined, flags=re.I):
                if i % LOG_EVERY_N == 0:
                    print(f"[SKIP] (no-keyword) {i}/{len(links_with_dates)} - {title[:120]}")
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue

            # extract details
            age, gender = find_age_gender(combined)
            cause, context = find_cause_and_context(combined)
            host = urlparse(url).netloc.lower().replace("www.", "")
            src = domain_to_source(host)
            seq_counters[src] = seq_counters.get(src, 0) + 1
            case_id = normalize_case_id(src, target_date, seq_counters[src])

            record = {
                "case_id": case_id,
                "reported_date": target_date,
                "state": None,
                "district": None,
                "gender": gender or "Unknown",
                "age": age if age is not None else None,
                "cause_of_death": cause,
                "reason_or_context": (context[:300] if context else None),
                "source_name": host,
                "source_url": url,
                "verified": True if host in DOMAIN_SOURCE_MAP else False
            }

            collected.append(record)
            seen_urls.add(url)
            print(f"[ACCEPT] {len(collected)} | {case_id} | {host} | age={record['age']} | gender={record['gender']} | cause={record['cause_of_death']}")
            time.sleep(DELAY_BETWEEN_REQUESTS)

        # safety: if reached global cap, break outer loop
        if total_links_tried > MAX_TOTAL_LINKS_TO_TRY:
            break

    # summary and save
    if collected:
        existing_by_url = {e.get("source_url"): e for e in existing if isinstance(e, dict)}
        new_records = [r for r in collected if r["source_url"] not in existing_by_url]
        final = existing + new_records
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final, f, indent=2, ensure_ascii=False)
        print(f"\n[DONE] Collected {len(collected)} candidates in this run; appended {len(new_records)} new records to {OUTPUT_FILE}.")
    else:
        print("\n[DONE] No new records collected in this run. No changes written to file.")

if __name__ == "__main__":
    run_scrape_interactive()
