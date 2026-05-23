
import csv
import os
import re
import time
import traceback
import random
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Constants — edit these to tune behaviour
# ---------------------------------------------------------------------------
HEADLESS = False            # False = visible browser window (recommended for debugging)
BROWSER_EXECUTABLE = "/usr/bin/google-chrome"  # System Chrome — avoids Playwright download
MAX_SCROLL_ATTEMPTS = 40    # How many scroll iterations to attempt before giving up
SCROLL_DISTANCE   = 800     # Pixels to scroll the feed panel per iteration
SCROLL_PAUSE_MIN  = 1.0     # Minimum seconds between scroll actions
SCROLL_PAUSE_MAX  = 3.0     # Maximum seconds between scroll actions
REQUEST_PAUSE_MIN = 0.8     # Minimum seconds between per-listing HTTP requests
REQUEST_PAUSE_MAX = 1.8     # Maximum seconds between per-listing HTTP requests
SETTLE_AFTER_SCROLL = 2.0   # Extra pause after the final scroll for DOM to settle
NUM_WORKERS       = 3      # Parallel browser sessions for Phase 2 detail fetching
END_OF_LIST_SENTINEL = "You've reached the end of the list"
OUTPUT_DIR     = "scrapper"
OUTPUT_PATTERN = "{category}_{city}_{date}.csv"


# ---------------------------------------------------------------------------
# URL Construction
# ---------------------------------------------------------------------------

def build_search_url(city: str, category: str) -> str:
    """Return the Google Maps search URL for the given category + city."""
    query = urllib.parse.quote_plus(f"{category} in {city}")
    return f"https://www.google.com/maps/search/{query}/"


# ---------------------------------------------------------------------------
# Scrolling (page_action callback)
# ---------------------------------------------------------------------------

def make_scroll_action(max_results: int):
    """
    Factory that captures max_results in a closure and returns a page_action
    callable with the signature Scrapling expects: (page) -> None.
    """

    def scroll_results(page) -> None:
        """
        Called by Scrapling after the initial page navigation completes.
        Receives a synchronous Playwright Page object.
        Scrolls div[role='feed'] until enough cards are visible or the list ends.
        """
        feed_sel = 'div[role="feed"]'

        for attempt in range(MAX_SCROLL_ATTEMPTS):
            # Count currently visible listing anchors
            cards = page.query_selector_all(f"{feed_sel} a.hfpxzc")
            count = len(cards)
            print(f"  [Scroll {attempt + 1}/{MAX_SCROLL_ATTEMPTS}] {count} results loaded...")

            if count >= max_results:
                print(f"  Target of {max_results} reached. Stopping scroll.")
                break

            feed_el = page.query_selector(feed_sel)
            if feed_el:
                # Check for the end-of-list sentinel before scrolling further
                if END_OF_LIST_SENTINEL in (feed_el.inner_text() or ""):
                    print("  End of results list detected. Stopping scroll.")
                    break
                # Scroll the feed panel element itself, not the whole window
                feed_el.evaluate(f"el => el.scrollBy(0, {SCROLL_DISTANCE})")
            else:
                # Fallback in case the feed panel selector has changed
                page.evaluate(f"window.scrollBy(0, {SCROLL_DISTANCE})")

            time.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))

        # Let the final batch of cards finish rendering before Scrapling parses the DOM
        time.sleep(SETTLE_AFTER_SCROLL)

    return scroll_results


# ---------------------------------------------------------------------------
# Data Extraction
# ---------------------------------------------------------------------------

def extract_listing(detail_page, fallback_name: str = "") -> dict:
    """
    Extract all required fields from a Google Maps business detail page.
    detail_page is a Scrapling Response (returned by session.fetch()).
    fallback_name is the aria-label value harvested from the list-card anchor.
    """

    def first_text(*selectors: str) -> str:
        for sel in selectors:
            val = detail_page.css(sel).get()
            if val and val.strip():
                return val.strip()
        return ""

    def first_attr(attr: str, *selectors: str) -> str:
        for sel in selectors:
            val = detail_page.css(f"{sel}::attr({attr})").get()
            if val and val.strip():
                return val.strip()
        return ""

    # --- Business name ---
    name = first_text(
        "h1.DUwDvf::text",
        "h1.DUwDvf.fontHeadlineLarge::text",
        "h1::text",
    ) or fallback_name

    # --- Numeric rating (e.g. "4.5") ---
    rating_raw = first_text(
        'div.F7nice > span > span[aria-hidden="true"]::text',
        "span.MW4etd::text",
        ".MW4etd::text",
    )
    try:
        rating = float(rating_raw) if rating_raw else ""
    except ValueError:
        rating = ""

    # --- Review count — keep digits only (handles "1,234 reviews" formatting) ---
    review_raw = first_text(
        "div.F7nice span.UY7F9::text",
        "button[aria-label*='reviews'] span::text",
        "span.UY7F9::text",
    )
    review_count = re.sub(r"[^\d]", "", review_raw) if review_raw else ""

    # --- Category shown on the listing (e.g. "Dentist", "Gym") ---
    category = first_text(
        "button.DkEaL::text",
        "div.skqShb button::text",
        "[jsaction*='category']::text",
    )

    # --- Full street address ---
    address = first_text(
        "button[data-item-id='address'] .Io6YTe::text",
        "button[data-item-id='address'] .fontBodyMedium::text",
        ".rogA2c .Io6YTe::text",
    )

    # --- Phone number ---
    phone = first_text(
        "button[data-item-id^='phone:tel:'] .Io6YTe::text",
        "button[data-item-id^='phone:'] .Io6YTe::text",
        "a[data-item-id^='phone:'] .Io6YTe::text",
        "[data-tooltip='Copy phone number'] .Io6YTe::text",
    )

    # --- Website URL (Google's "authority" data-item-id is their stable internal key) ---
    website = first_attr(
        "href",
        "a[data-item-id='authority']",
        "a[data-item-id^='authority']",
        "a[aria-label*='website']",
        "a[aria-label*='Website']",
    )

    return {
        "business_name": name,
        "phone":         phone,
        "category":      category,
        "website":       website,
        "has_website":   "Yes" if website else "No",
        "rating":        rating,
        "review_count":  review_count,
        "address":       address,
    }


# ---------------------------------------------------------------------------
# Parallel chunk worker
# ---------------------------------------------------------------------------

def scrape_chunk(items: list, target: int) -> list:
    """
    Fetch and extract detail pages for a subset of listings.
    Opens its own DynamicSession so threads don't share browser state.
    items: list of (index, href, fallback_name) tuples.
    target: total listing count — used only for progress output.
    """
    local_results = []

    from scrapling.fetchers import DynamicSession

    with DynamicSession(
        headless=HEADLESS,
        network_idle=True,
        executable_path=BROWSER_EXECUTABLE,
    ) as session:
        for i, href, fallback_name in items:
            try:
                detail_page = session.fetch(href, wait_selector="h1")
                data = extract_listing(detail_page, fallback_name)
                local_results.append(data)
                print(f"[{i + 1}/{target}] Scraped: {data['business_name']}")
            except Exception as exc:
                print(f"[{i + 1}/{target}] ERROR fetching {href} ({fallback_name!r}): {exc}")

            time.sleep(random.uniform(REQUEST_PAUSE_MIN, REQUEST_PAUSE_MAX))

    return local_results


# ---------------------------------------------------------------------------
# CSV Output
# ---------------------------------------------------------------------------

def save_to_csv(rows: list, path: str) -> None:
    """Keep only businesses with no website, sort by rating descending, write CSV."""

    # Only save listings that have no website
    filtered = [r for r in rows if r.get("has_website") == "No"]

    def sort_key(row: dict):
        r = row.get("rating", "")
        # (0, -rating) sorts rated entries highest-first;
        # (1, 0.0) pushes unrated entries to the end.
        return (0, -float(r)) if r != "" else (1, 0.0)

    fieldnames = [
        "business_name",
        "phone",
        "category",
        "website",
        "has_website",
        "rating",
        "review_count",
        "address",
    ]

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(filtered, key=sort_key))


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    city      = input("Enter city/town name  (e.g. Pimpri-Chinchwad): ").strip()
    category  = input("Enter business category (e.g. dentists, gyms): ").strip()
    max_input = input("Max results to scrape [default 50]: ").strip()

    try:
        max_results = int(max_input)
    except ValueError:
        max_results = 50

    search_url = build_search_url(city, category)
    print(f"\nSearch URL : {search_url}")
    print(f"Target     : {max_results} results\n")

    from scrapling.fetchers import DynamicSession

    scroll_action = make_scroll_action(max_results)

    # ------------------------------------------------------------------
    # Phase 1 — scroll the results feed and collect card links
    # ------------------------------------------------------------------
    print("=== Phase 1: Loading results list ===")
    with DynamicSession(
        headless=HEADLESS,
        network_idle=True,
        executable_path=BROWSER_EXECUTABLE,
    ) as session:
        list_page = session.fetch(
            search_url,
            page_action=scroll_action,
            wait_selector='div[role="feed"]',
        )
        card_links = list_page.css('div[role="feed"] a.hfpxzc')

        total_found = len(card_links)
        target      = min(total_found, max_results)
        print(f"\nFound {total_found} cards. Will scrape {target}.\n")

        # Extract plain strings while the session (and its DOM) is still alive
        items = [
            (
                i,
                anchor.css("::attr(href)").get() or "",
                anchor.css("::attr(aria-label)").get() or "",
            )
            for i, anchor in enumerate(card_links[:target])
        ]

    # Drop any cards that have no href
    items = [(i, href, name) for i, href, name in items if href]
    target = len(items)

    # ------------------------------------------------------------------
    # Phase 2 — fetch detail pages in parallel across NUM_WORKERS threads
    # ------------------------------------------------------------------
    print(f"=== Phase 2: Extracting listing details ({NUM_WORKERS} workers) ===")

    # Split items into NUM_WORKERS interleaved chunks so work is distributed evenly
    chunks = [items[w::NUM_WORKERS] for w in range(NUM_WORKERS)]

    results: list = []
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {
            executor.submit(scrape_chunk, chunk, target): w
            for w, chunk in enumerate(chunks)
            if chunk
        }
        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as exc:
                w = futures[future]
                lost = len(chunks[w])
                print(f"[Worker {w}] fatal error — {lost} items lost: {exc}")
                traceback.print_exc()

    if not results:
        print("\nNo results collected. Exiting.")
        return

    # Build output path: scrapper/{city}/{category}/{category}_{city}_{date}.csv
    date_str  = datetime.now().strftime("%Y%m%d")
    safe_cat  = re.sub(r"\s+", "_", category.lower())
    safe_city = re.sub(r"\s+", "_", city.lower())
    out_dir   = os.path.join(OUTPUT_DIR, safe_city, safe_cat)
    os.makedirs(out_dir, exist_ok=True)
    filename  = os.path.join(out_dir, OUTPUT_PATTERN.format(category=safe_cat, city=safe_city, date=date_str))

    save_to_csv(results, filename)

    with_web    = sum(1 for r in results if r["has_website"] == "Yes")
    without_web = len(results) - with_web
    print(f"\n{'=' * 52}")
    print("  SCRAPING COMPLETE")
    print(f"{'=' * 52}")
    print(f"  Total scraped    : {len(results)}")
    print(f"  With website     : {with_web}  (skipped — not saved)")
    print(f"  Without website  : {without_web}  (saved to CSV, sorted by rating)")
    print(f"  Output file      : {filename}")
    print(f"{'=' * 52}\n")


if __name__ == "__main__":
    main()
