"""
Scrapers package for ProxyGather.

This package contains various scrapers for different proxy sources.
"""

from .proxy_scraper import scrape_proxies, extract_proxies_from_content
from .proxyscrape_api_fetcher import fetch_from_api
from .geonode_scraper import scrape_from_geonode_api
from .proxydb_scraper import scrape_all_from_proxydb
from .checkerproxy_scraper import scrape_checkerproxy_archive
from .proxylistorg_scraper import scrape_from_proxylistorg
from .xseo_scraper import scrape_from_xseo
from .gologin_scraper import scrape_from_gologin_api
from .proxyhttp_scraper import scrape_from_proxyhttp
from .proxydocker_scraper import scrape_from_proxydocker
from .advancedname_scraper import scrape_from_advancedname
from .proxyservers_scraper import scrape_from_proxyservers
from .proxydaily_scraper import scrape_from_proxydaily
from .proxynova_scraper import scrape_from_proxynova
from .premproxy_scraper import scrape_from_premproxy
from .source_discoverer import discover_urls_from_file, convert_to_jsdelivr_url

__all__ = [
    'scrape_proxies',
    'extract_proxies_from_content',
    'fetch_from_api',
    'scrape_from_geonode_api',
    'scrape_all_from_proxydb',
    'scrape_checkerproxy_archive',
    'scrape_from_proxylistorg',
    'scrape_from_xseo',
    'scrape_from_gologin_api',
    'scrape_from_proxyhttp',
    'scrape_from_proxydocker',
    'scrape_from_advancedname',
    'scrape_from_proxyservers',
    'scrape_from_proxydaily',
    'scrape_from_proxynova',
    'scrape_from_premproxy',
    'discover_urls_from_file',
    'convert_to_jsdelivr_url',
]
