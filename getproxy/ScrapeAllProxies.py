import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from all our library packages
from scrapers.proxy_scraper import scrape_proxies
from scrapers.proxyscrape_api_fetcher import fetch_from_api
from scrapers.proxydb_scraper import scrape_all_from_proxydb
from scrapers.geonode_scraper import scrape_from_geonode_api
from scrapers.checkerproxy_scraper import scrape_checkerproxy_archive
from scrapers.proxylistorg_scraper import scrape_from_proxylistorg


# from scrapers.spysone_scraper import scrape_from_spysone

# --- Configuration ---
SITES_FILE = 'sites-to-get-proxies-from.txt'
OUTPUT_FILE = 'scraped-proxies.txt'
# Set the maximum number of parallel scrapers to run
MAX_WORKERS = 6 # Increased for the new task

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
    Main function to run all scrapers concurrently, combine results, and save them.
    """
    # A dictionary to hold the functions to run and their friendly names
    scraper_tasks = {
        'ProxyScrape API': fetch_from_api,
        'ProxyDB': scrape_all_from_proxydb,
        'Geonode API': scrape_from_geonode_api,
        'CheckerProxy Archive': scrape_checkerproxy_archive,
        'ProxyList.org': scrape_from_proxylistorg, 
    }
    
    # --- Prepare the website scraping task separately ---
    try:
        with open(SITES_FILE, 'r') as f:
            urls_to_scrape = [line.strip() for line in f if line.strip()]
        if not urls_to_scrape:
             print(f"[WARN] The URL file '{SITES_FILE}' is empty. Skipping generic website scraping.")
        else:
             # Add the website scraper to the tasks if URLs are present.
             scraper_tasks[f'Websites ({SITES_FILE})'] = lambda: scrape_proxies(urls_to_scrape, verbose=False)
    except FileNotFoundError:
        print(f"[ERROR] The file '{SITES_FILE}' was not found. Skipping generic website scraping.")
    
    # This dictionary will hold the results from each scraper
    results = {}

    print(f"--- Starting {len(scraper_tasks)} scrapers concurrently (max workers: {MAX_WORKERS}) ---")

    # --- Run all scrapers in parallel ---
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Create a future for each scraper task
        future_to_scraper = {executor.submit(func): name for name, func in scraper_tasks.items()}
        
        # Process futures as they complete
        for future in as_completed(future_to_scraper):
            scraper_name = future_to_scraper[future]
            try:
                # Get the list of proxies from the completed future
                proxies_found = future.result()
                results[scraper_name] = proxies_found
                print(f"[COMPLETED] '{scraper_name}' finished, found {len(proxies_found)} proxies.")
            except Exception as e:
                print(f"[ERROR] Scraper '{scraper_name}' failed with an exception: {e}")
                results[scraper_name] = [] # Store empty list on failure

    # --- Combine, Deduplicate, and Clean all results ---
    print("\n--- Combining and processing all results ---")
    
    # Combine lists of proxies from the results dictionary
    combined_proxies = []
    for proxy_list in results.values():
        combined_proxies.extend(proxy_list)
    
    non_empty_proxies = [p for p in combined_proxies if p and p.strip()]
    unique_proxies = set(non_empty_proxies)
    final_proxies = sorted(list(unique_proxies))
    
    print("\n--- Summary ---")
    # Print the summary in a consistent, sorted order
    for name in sorted(results.keys()):
        print(f"Found {len(results.get(name, []))} proxies from {name}.")
    
    print(f"\nTotal unique proxies after cleaning and deduplication: {len(final_proxies)}")

    # --- Save the final list ---
    if not final_proxies:
        print("\nCould not find any proxies from any source.")
    else:
        save_proxies_to_file(final_proxies, OUTPUT_FILE)


if __name__ == "__main__":
    main()