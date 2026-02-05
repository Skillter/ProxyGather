# The Ultimate Proxy Scraper & Checker

This project is a sophisticated tool designed to scrape proxies from a wide variety of sources and check them for validity and performance.

Additionally the scraper runs every 30 minutes on its own via GitHub Actions, ensuring the proxy lists are always fresh.

If you find this project useful, **please consider giving it a star ⭐** or share it by the word of mouth. Those things help a lot. thanks.

### Index
- [Live Proxy Lists](#live-proxy-lists)
- [Notice](#Notice)
- [Installation](#installation)
- [Advanced Usage](#advanced-usage)
- [Adding Your Own Sites](#adding-your-own-sites)
- [What Makes This Project Different?](#so-what-makes-this-project-different-from-other-proxy-scrapers)
- [Contributions](#contributions)

## Live Proxy Lists

These URLs link directly to the raw, automatically-updated proxy lists. You can integrate them right into your projects.

*   **Working Proxies (Checked and Recommended):**
    *   All Protocols: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-all.txt`
    *   HTTP: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-http.txt`
    *   SOCKS4: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks4.txt`
    *   SOCKS5: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks5.txt`
*   **All Scraped Unchecked Proxies (Most are dead):** `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/scraped-proxies.txt`

## Notice

I do not host the provided proxies. The code is design to only **collect publicly listed proxies** from websites and check if they are working. Remember that **some public proxies are intentionally malicious**, so **never** send your passwords or any sensitive data while connected to any public proxy to be safe. I built this tool to make it easier for developers and power-users to access resources for building/creating things, because I believe skill and talent shouldn't be wasted by no budget. **I condemn malicious use**, please use proxies responsibly. 

## Installation

Getting up and running is fast and simple. *Tested on Python 3.12.9*

1.  **Clone the repository and install packages:** 
    ```bash
    git clone https://github.com/Skillter/ProxyGather.git
    cd ProxyGather
    pip install -r requirements.txt
    ```

2.  **Run It**

    Execute the script. Default settings make it work out-of-box.
    The results are in the same folder.
    ```bash
    python ProxyGather.py run
    ```

## Advanced Usage

For more control, you can use these command-line arguments.

### Scraping Proxies
```bash
python ProxyGather.py scrape --output proxies/scraped.txt --scraper-threads 75 --exclude Webshare ProxyDB --remove-dead-links
```

#### Arguments:

*   `--output`: Specify the output file for the scraped proxies. (Default: `scraped-proxies.txt`)
*   `--scraper-threads`: Number of concurrent threads to use for the general scrapers. (Default: 50)
*   `--automation-threads`: Number of concurrent threads for browser automation scrapers. (Default: 3)
*   `--only`: Run only specific scrapers. For example: `--only Geonode ProxyDB`
*   `--exclude`: Run all scrapers except for specific ones. For example: `--exclude Webshare`
*   `-v`, `--verbose`: Enable detailed logging for what's being scraped.
*   `--remove-dead-links`: Automatically remove URLs from `sites-to-get-proxies-from.txt` that yield no proxies.
*   `--compliant`: Run in compliant mode (respects robots.txt, no anti-bot bypass).
*   `--use-browser-automation`: Enable browser automation scrapers (Hide.mn, OpenProxyList, Spys.one).
*   `-y`, `--yes`: Auto-accept the legal disclaimer.

To see a list of all available scrapers, run: `python ProxyGather.py scrape --only`

#### Available Sources:
*   **Websites** - URLs from `sites-to-get-proxies-from.txt`
*   **Discover** - URLs discovered from website lists in `sites-to-get-sources-from.txt`
*   **Advanced.name**
*   **CheckerProxy**
*   **Geonode**
*   **GoLogin**
*   **Hide.mn** (Pass `--use-browser-automation` to enable)
*   **OpenProxyList** (Pass `--use-browser-automation` to enable)
*   **PremProxy**
*   **Proxy-Daily**
*   **ProxyDB**
*   **ProxyDocker**
*   **ProxyHttp**
*   **ProxyList.org**
*   **ProxyNova**
*   **ProxyScrape**
*   **ProxyServers.pro**
*   **Spys.one** (Pass `--use-browser-automation` to enable)

### Checking Proxies

```bash
python ProxyGather.py check --input proxies/scraped.txt --output proxies/working.txt --checker-threads 2000 --timeout 5s --verbose --prepend-protocol
```

#### Arguments:

*   `--input`: The input file(s) containing the proxies to check. You can use wildcards. (Default: `scraped-proxies.txt`)
*   `--output`: The base name for the output files. The script will create separate files for each protocol (e.g. `working-http.txt`, `working-socks5.txt`).
*   `--checker-threads`: The number of concurrent threads to use for checking. (Default: 500)
*   `--timeout`: The timeout for each proxy check (e.g. `8s`, `500ms`). (Default: `6s`)
*   `-v`, `--verbose`: Enable detailed logging
*   `--prepend-protocol`: Add the protocol prefix (e.g. "http://", "socks5://") to the start of each line

### Unified Mode (Scrape + Check)

```bash
python ProxyGather.py run --scraper-threads 50 --checker-threads 500 --timeout 6s
```

This runs both scraping and checking in one command with a streaming pipeline. Scraped proxies are immediately fed to the checker for validation.

#### Arguments:

*   `--scraper-output`: Output file for scraped proxies. (Default: `scraped-proxies-{timestamp}.txt`)
*   `--checker-input`: Additional proxy file(s) to check alongside scraped proxies. Useful for re-checking existing lists.
*   `--checker-output`: Base name for working proxy output files. (Default: `working-proxies-{timestamp}`)
*   `--scraper-threads`: Number of concurrent threads for scraping. (Default: 50)
*   `--checker-threads`: Number of concurrent threads for checking. (Default: 500)
*   `--timeout`: Timeout for each proxy check (e.g. `8s`, `500ms`). (Default: `6s`)
*   `--automation-threads`: Concurrent threads for browser automation scrapers. (Default: 3)
*   `--only`: Run only specific scrapers. (See `scrape --only` for list)
*   `--exclude`: Exclude specific scrapers.
*   `--compliant`: Run in compliant mode (respects robots.txt, no anti-bot bypass).
*   `--use-browser-automation`: Enable browser automation scrapers.
*   `-y`, `--yes`: Auto-accept the legal disclaimer.
*   `-v`, `--verbose`: Enable detailed logging.

#### Example: Check Existing Proxies + Scrape New Ones

```bash
python ProxyGather.py run \
  -y \
  --checker-input proxies/existing-proxies.txt \
  --checker-output proxies/working-proxies \
  --scraper-output proxies/scraped-proxies.txt \
  --checker-threads 1300 \
  --timeout 3s
```

This will:
1. Load proxies from `proxies/existing-proxies.txt` into the checker
2. Scrape new proxies from all sources
3. Check all proxies (existing + scraped)
4. Save working proxies to `proxies/working-proxies-all.txt` (and `-http.txt`, `-socks4.txt`, `-socks5.txt`)

## Adding Your Own Sites

You can easily add an unlimited number of your own targets by editing the `sites-to-get-proxies-from.txt` file. It uses a simple format:

`URL|{JSON_PAYLOAD}|{JSON_HEADERS}`

*   **URL**: The only required part.
*   **JSON\_PAYLOAD**: (Optional) A JSON object for POST requests. Use `{page}` as a placeholder for page numbers in paginated sites.
*   **JSON\_HEADERS**: (Optional) A JSON object for custom request headers.

#### Examples:

```
# Simple GET request
https://www.myproxysite.com/public-list

# Paginated POST request
https://api.proxies.com/get|{"page": "{page}", "limit": 100}|{"Authorization": "Bearer my-token"}

# No payload, but custom headers
https://api.proxies.com/get||{"Authorization": "Bearer my-token"}
```

## So what makes this project different from other proxy scrapers?

*   **Advanced Anti-Bot Evasion**: This isn't just a simple script. It includes dedicated logic for websites that use advanced anti-bot measures like session validation, Recaptcha fingerprinting or even required account registration.
It can parse JavaScript-obfuscated IPs, decode Base64-encoded proxies, handle paginated API calls, and in cases where it's required, an automated browser ([SeleniumBase](https://github.com/seleniumbase/SeleniumBase)) to bypass the detection and unlock exclusive proxies that other tools can't reach.

*   **A Checker That's Actually Smart**: Most proxy checkers just see if a port is open. That's not good enough. A proxy can be "alive" but useless or even malicious. This engine's validator is more sophisticated.
    *   **Detects Hijacking**: It sends a request to a trusted third-party 'judge'. If a proxy returns some weird ad page or incorrect content instead of the real response, it's immediately flagged as a potential **hijack** and discarded. This is a common issue with free proxies that this checker actively prevents.
    *   **Identifies Password Walls**: If a proxy requires a username and password (sending a `407` status), it's correctly identified and discarded.
    *   **Weeds Out Misconfigurations**: The checker looks for sensible, stable connections. If a proxy connects but then immediately times out or returns nonsensical errors, it's dropped. This cleans up the final list by removing thousands of unstable or poorly configured proxies.

The result is a cleaner, far more reliable list of proxies you can actually use, not just a list of open ports.

*   **Automated Fresh List**: Thanks to GitHub Actions, the entire process of scraping, checking, and committing the results is automated every 30 minutes. You can simply grab the fresh working proxies from a link to the raw file.
*   **Easily add more sources**: Easily add your own targets to the `sites-to-get-proxies-from.txt` file, for the sites that don't use obfuscation.

## Contributions

Contributions are what makes the open-source community thrive. Any contributions you make are **warmly welcomed**! Whether it's suggesting a new proxy source, adding a new scraper, improving the checker or fixing a bug, feel free to open an issue or send a pull request.
*Note: The project has been developed and tested on Python 3.12.9*
