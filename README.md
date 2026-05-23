# Google Maps Scraper

A powerful Python-based web scraper for collecting business information from Google Maps search results. This tool uses **Scrapling** (a browser automation library) to extract business details like name, rating, phone, address, website, and more.

## Features

- **Two-Phase Scraping**: Efficiently loads search results via scrolling, then fetches detailed business information in parallel
- **Parallel Processing**: Uses multithreading to speed up detail page extraction (configurable workers)
- **Intelligent Filtering**: Automatically filters out businesses with websites and sorts results by rating
- **Robust Extraction**: Multiple CSS selectors for each field to handle Google Maps DOM variations
- **Anti-Detection**: Randomized request delays and headless browser options to mimic natural browsing
- **CSV Export**: Organized output with businesses sorted by rating (highest first)

## Setup

Follow these steps to create an isolated environment, install dependencies, and run the project.

### 1) Python version
- Recommended: Python 3.10+ (works with 3.8+, but 3.10+ is recommended).

### 2) Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
```

On Windows (Command Prompt):
```cmd
.venv\Scripts\activate.bat
```

### Windows notes
- Activate the virtual environment using PowerShell or Command Prompt (examples above).
- Chrome/Chromium path example on Windows: `C:\Program Files\Google\Chrome\Application\chrome.exe`.
  - Edit the `BROWSER_EXECUTABLE` constant in `gmaps_scraper.py` to match your install path, for example:
    ```python
    BROWSER_EXECUTABLE = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    ```
- If you prefer Playwright-managed browsers on Windows:
  ```powershell
  pip install playwright
  playwright install
  ```
  Run the script after installing browsers:
  ```powershell
  python gmaps_scraper.py
  ```

Note: On some Windows setups PowerShell's execution policy blocks `Activate.ps1`. If you see an error about running scripts, either run PowerShell as Administrator and set `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, or use the Command Prompt activation shown above.

### 3) Install dependencies
Install runtime and test dependencies from `requirements.txt`:
```bash
pip install -U pip
pip install -r requirements.txt
```

Notes:
- The scraper uses a system Chrome/Chromium binary by default (`BROWSER_EXECUTABLE = /usr/bin/google-chrome`).
- If you prefer to use Playwright-managed browsers, install Playwright and its browsers:
  ```bash
  pip install playwright
  playwright install
  ```

### 4) Verify the setup
Run the script interactively:
```bash
python gmaps_scraper.py
```

Run the test suite:
```bash
pytest tests/ -q
```

## Usage

Run the scraper interactively:
```bash
python gmaps_scraper.py
```

You'll be prompted for:
1. **City/Town Name** (e.g., "Pimpri-Chinchwad", "Mumbai")
2. **Business Category** (e.g., "dentists", "gyms", "restaurants")
3. **Max Results** (default: 50)

### Example Output
```
Enter city/town name  (e.g. Pimpri-Chinchwad): Pimpri-Chinchwad
Enter business category (e.g. dentists, gyms): dentists
Max results to scrape [default 50]: 50

Search URL : https://www.google.com/maps/search/dentists+in+Pimpri-Chinchwad/
Target     : 50 results

=== Phase 1: Loading results list ===
  [Scroll 1/40] 10 results loaded...
  [Scroll 2/40] 20 results loaded...
  ...
Found 45 cards. Will scrape 45.

=== Phase 2: Extracting listing details (3 workers) ===
[1/45] Scraped: Smile Dental Clinic
[2/45] Scraped: Dr. Patel's Dental Care
...

====================================================
  SCRAPING COMPLETE
====================================================
  Total scraped    : 45
  With website     : 12  (skipped — not saved)
  Without website  : 33  (saved to CSV, sorted by rating)
  Output file      : scrapper/pimpri_chinchwad/dentists/dentists_pimpri_chinchwad_20260523.csv
====================================================
```

## Configuration

Edit constants in `gmaps_scraper.py` to customize behavior:

| Setting | Default | Purpose |
|---------|---------|---------|
| `HEADLESS` | `False` | Show browser window (set to `True` for background operation) |
| `BROWSER_EXECUTABLE` | `/usr/bin/google-chrome` | Path to Chrome browser |
| `MAX_SCROLL_ATTEMPTS` | 40 | Maximum scroll iterations before stopping |
| `SCROLL_DISTANCE` | 800 | Pixels scrolled per iteration |
| `SCROLL_PAUSE_MIN` / `SCROLL_PAUSE_MAX` | 1.0 / 3.0 | Random delay between scrolls (seconds) |
| `REQUEST_PAUSE_MIN` / `REQUEST_PAUSE_MAX` | 0.8 / 1.8 | Random delay between requests (seconds) |
| `NUM_WORKERS` | 3 | Parallel threads for detail fetching |
| `OUTPUT_DIR` | `scrapper` | Base output directory |

## Extracted Fields

Each CSV file contains the following columns:

- **business_name**: Business name
- **phone**: Phone number
- **category**: Business category (e.g., "Dentist", "Gym")
- **website**: Website URL (if available)
- **has_website**: Yes/No flag
- **rating**: Numeric rating (e.g., 4.5)
- **review_count**: Number of reviews
- **address**: Full street address

## Output Structure

Results are saved to:
```
scrapper/
├── {city}/
│   └── {category}/
│       └── {category}_{city}_{YYYYMMDD}.csv
```

Example: `scrapper/pimpri_chinchwad/dentists/dentists_pimpri_chinchwad_20260523.csv`

## Testing

Run the test suite:
```bash
pytest tests/
```

Or with verbose output:
```bash
pytest tests/ -v
```

### Test Coverage
- URL encoding and special character handling
- CSV filtering (removes businesses with websites)
- CSV sorting (by rating, highest first)
- Unrated entry handling

## How It Works

### Phase 1: Results Discovery
1. Loads Google Maps search page for `{category} in {city}`
2. Scrolls the results feed panel until target count or end-of-list reached
3. Extracts hrefs and labels from visible result cards

### Phase 2: Detail Extraction
1. Distributes URLs across `NUM_WORKERS` parallel threads
2. Each worker opens a separate browser session to avoid race conditions
3. Fetches detail pages and extracts business information using CSS selectors
4. Adds randomized delays between requests to avoid rate limiting

### Phase 3: Filtering & Export
1. Filters out businesses with websites (focuses on those needing digital presence)
2. Sorts remaining results by rating (highest first)
3. Exports to CSV with timestamp and city/category hierarchy

## Important Legal Notice

⚠️ **Scraping Google Maps violates Google's Terms of Service.**

This tool is intended for **educational and research purposes only**. For production or commercial use, please use one of these legitimate alternatives:

- **[Google Places API](https://developers.google.com/maps/documentation/places/web-service/overview)** - Official Google service with quotas and pricing
- **[OpenStreetMap Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API)** - Free, open-source alternative
- **[Yelp Fusion API](https://www.yelp.com/developers)** - Business data with proper licensing

## Troubleshooting

**Issue**: Chrome not found
```
Fix: Update BROWSER_EXECUTABLE in gmaps_scraper.py to your Chrome path
Example: /opt/google/chrome/google-chrome (Linux)
         /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome (macOS)
         C:\Program Files\Google\Chrome\Application\chrome.exe (Windows)
```

**Issue**: Timeout errors during scrolling
```
Fix: Increase MAX_SCROLL_ATTEMPTS or SETTLE_AFTER_SCROLL
Check your internet connection and Google Maps availability
```

**Issue**: Few/no results extracted
```
Fix: Verify the category name is correct (e.g., use "dentists" not "dentist")
Wait for page load to complete (check visible results)
Try increasing MAX_SCROLL_ATTEMPTS
```

## Architecture

- **Two-Phase Design**: Separates discovery (single browser, aggressive scrolling) from detail extraction (multiple browsers, gentle requests)
- **ThreadPoolExecutor**: Distributes chunks of URLs evenly across workers for load balancing
- **DOM Robustness**: Multiple selectors for each field handle Google's frequent layout changes
- **Session Management**: Each worker opens fresh DynamicSession to avoid memory leaks and state conflicts

## Performance Notes

- Typical extraction: **30-60 seconds** per business (depends on page load and randomized delays)
- Parallel workers significantly reduce total runtime (e.g., 3 workers ≈ 3x faster than serial)
- Large result sets (500+) may take 10-20+ minutes with default delays
- Consider increasing delays (`SCROLL_PAUSE_MAX`, `REQUEST_PAUSE_MAX`) to reduce detection risk

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Contact

For questions or feedback, please open an issue on GitHub.

---

**Last Updated**: May 2026
