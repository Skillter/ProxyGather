# The Ultimate Proxy Scraper & Checker

This project is a sophisticated tool designed to scrape proxies from a wide variety of sources and check them for validity and performance.

Additionally the scraper runs every 30 minutes on its own via GitHub Actions, ensuring the proxy lists are always fresh.

If you find this project useful, **please consider giving it a star ⭐** or share it by the word of mouth. Those things help a lot. thanks.

### Index
- [What Makes This Project Different?](#so-what-makes-this-project-different-from-other-proxy-scrapers)
- [Live Proxy Lists](#live-proxy-lists)
- [Installation](#installation)
- [Advanced Usage](#advanced-usage)
- [Adding Your Own Sites](#adding-your-own-sites)
- [Contributions](#contributions)


## So what makes this project different from other proxy scrapers?

*   **Advanced Anti-Bot Evasion**: This isn't just a simple script. It includes dedicated logic for websites that use advanced anti-bot measures like session validation, Recaptcha fingerprinting or even required account registration.
It can parse JavaScript-obfuscated IPs, decode Base64-encoded proxies, handle paginated API calls, and in cases where it's required, a headless automated browser (`undetected-chromedriver`) to trick the detection to unlock exclusive proxies that other tools can't reach.

*   **A Checker That's Actually Smart**: Most proxy checkers just see if a port is open. That's not good enough. A proxy can be "alive" but useless or even malicious. This engine's validator is more sophisticated.
    *   **Detects Hijacking**: It sends a request to a trusted third-party 'judge'. If a proxy returns some weird ad page or incorrect content instead of the real response, it's immediately flagged as a potential **hijack** and discarded. This is a common issue with free proxies that this checker actively prevents.
    *   **Identifies Password Walls**: If a proxy requires a username and password (sending a `407` status), it’s correctly identified and discarded.
    *   **Weeds Out Misconfigurations**: The checker looks for sensible, stable connections. If a proxy connects but then immediately times out or returns nonsensical errors, it's dropped. This cleans up the final list by removing thousands of unstable or poorly configured proxies.

The result is a cleaner, far more reliable list of proxies you can actually use, not just a list of open ports.

*   **Automated Fresh List**: Thanks to GitHub Actions, the entire process of scraping, checking, and committing the results is automated every 30 minutes. You can simply grab the fresh working proxies from a link to the raw file.
*   **Easily add more sources**: Easily add your own targets to the `sites-to-get-proxies-from.txt` file, for the sites that don't use obfuscation.

## Live Proxy Lists

These URLs link directly to the raw, automatically-updated proxy lists. You can integrate them right into your projects.

*   **Working Proxies (Checked and Recommended):**
    *   All Protocols: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-all.txt`
    *   HTTP: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-http.txt`
    *   SOCKS4: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks4.txt`
    *   SOCKS5: `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks5.txt`
*   **All Scraped Unchecked Proxies (Most are dead):** `https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/scraped-proxies.txt`

## Installation

Getting up and running is fast and simple. *Tested on Python 3.12.9*

1.  **Clone the repository and install packages:** 
    ```bash
    git clone https://github.com/Skillter/ProxyGather.git
    cd ProxyGather
    pip install -r requirements.txt
    ```

2.  **Run It**

    Execute the scripts. Default settings make it work out-of-box.
    The results are in the same folder.
    ```bash
    python ScrapeAllProxies.py
    python CheckProxies.py
    ```

## Advanced Usage

For more control, you can use these command-line arguments.

### Scraping Proxies
```bash
python ScrapeAllProxies.py --output proxies/scraped.txt --threads 75 --exclude Webshare ProxyDB --remove-dead-links
```

#### Arguments:

*   `--output`: Specify the output file for the scraped proxies. (Default: `scraped-proxies.txt`)
*   `--threads`: Number of concurrent threads to use for the general scrapers. (Default: 50)
*   `--only`: Run only specific scrapers. For example: `--only Geonode ProxyDB`
*   `--exclude`: Run all scrapers except for specific ones. For example: `--exclude Webshare`
*   `-v`, `--verbose`: Enable detailed logging for what's being scraped.
*   `--remove-dead-links`: Automatically remove URLs from `sites-to-get-proxies-from.txt` that yield no proxies.

To see a list of all available scrapers, run: `python ScrapeAllProxies.py --only`

### Checking Proxies

```bash
python CheckProxies.py --input proxies/scraped.txt --output proxies/working.txt --threads 2000 --timeout 5s --verbose --prepend-protocol
```

#### Arguments:

*   `--input`: The input file(s) containing the proxies to check. You can use wildcards. (Default: `scraped-proxies.txt`)
*   `--output`: The base name for the output files. The script will create separate files for each protocol (e.g. `working-http.txt`, `working-socks5.txt`).
*   `--threads`: The number of concurrent threads to use for checking. (Default: 100)
*   `--timeout`: The timeout for each proxy check (e.g. `8s`, `500ms`). (Default: `8s`)
*   `-v`, `--verbose`: Enable detailed logging for failed checks.
*   `--prepend-protocol`: Add the protocol prefix (e.g. "http://", "socks5://") to the start of each line

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

## Contributions

Contributions are what makes the open-source community thrive. Any contributions you make are **warmly welcomed**! Whether it's suggesting a new proxy source, adding a new scraper, improving the checker or fixing a bug, feel free to open an issue or send a pull request.
*Note: The project has been developed and tested on Python 3.12.9*
