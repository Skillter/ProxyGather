import sys
# Import from all our library packages
from scrapers.proxy_scraper import scrape_proxies
from scrapers.proxyscrape_api_fetcher import fetch_from_api
from scrapers.proxydb_scraper import scrape_all_from_proxydb # New import

# --- Configuration ---
SITES_FILE = 'sites-to-get-proxies-from.txt'
OUTPUT_FILE = 'scraped-proxies.txt'

def save_proxies_to_file(proxies: list, filename: str):
    """Saves a list of proxies to a text file, one per line."""
    try:
        with open(filename, 'w') as f:
            for proxy in proxies:
                f.write(proxy + '\n')
        print(f"\n[SUCCESS] Successfully saved {len(proxies)} unique proxies to '{filename}'")
    except IOError as e:
        print(f"\n[ERROR] Could not write to file '{filename}': {e}")

def main():
    """
    Main function to run all scrapers, combine results, and save them.
    """
    scraped_proxies = []
    api_proxies = []
    proxydb_proxies = []

    # --- 1. Scrape from the list of websites in the text file ---
    print(f"--- Scraping from sites in '{SITES_FILE}' ---")
    try:
        with open(SITES_FILE, 'r') as f:
            urls_to_scrape = [line.strip() for line in f if line.strip()]
        if not urls_to_scrape:
             print("[WARN] The URL file is empty. Skipping website scraping.")
             scraped_proxies = []
        else:
             print(f"Found {len(urls_to_scrape)} URLs to process.")
             scraped_proxies = scrape_proxies(urls_to_scrape, verbose=True)
    except FileNotFoundError:
        print(f"[ERROR] The file '{SITES_FILE}' was not found. Skipping website scraping.")
        scraped_proxies = []
    
    # --- 2. Fetch proxies from the ProxyScrape API ---
    print("\n--- Fetching from ProxyScrape API ---")
    api_proxies = fetch_from_api(verbose=True)

    # --- 3. Scrape all pages from ProxyDB ---
    print("\n--- Scraping all pages from ProxyDB ---")
    proxydb_proxies = scrape_all_from_proxydb(verbose=True)

    # --- 4. Combine, Deduplicate, and Clean all results ---
    print("\n--- Combining and processing all results ---")
    
    # Combine the lists from all three sources
    combined_proxies = scraped_proxies + api_proxies + proxydb_proxies
    
    # Filter out any empty or whitespace-only strings
    non_empty_proxies = [p for p in combined_proxies if p and p.strip()]

    # Using a set is the most efficient way to get unique items
    unique_proxies = set(non_empty_proxies)
    
    # Convert back to a list and sort it for consistent output
    final_proxies = sorted(list(unique_proxies))
    
    print("\n--- Summary ---")
    print(f"Found {len(scraped_proxies)} proxies from websites in {SITES_FILE}.")
    print(f"Found {len(api_proxies)} proxies from the API.")
    print(f"Found {len(proxydb_proxies)} proxies from ProxyDB.")
    print(f"Total unique proxies after cleaning and deduplication: {len(final_proxies)}")

    # --- 5. Save the final list ---
    if not final_proxies:
        print("\nCould not find any proxies from any source.")
    else:
        save_proxies_to_file(final_proxies, OUTPUT_FILE)


if __name__ == "__main__":
    main()