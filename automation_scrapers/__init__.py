"""
Automation scrapers package for ProxyGather.

This package contains browser automation-based scrapers for sites with
advanced anti-bot measures (Cloudflare, CAPTCHAs, etc.).
"""

from .spysone_scraper import scrape_from_spysone
from .openproxylist_scraper import scrape_from_openproxylist
from .hidemn_scraper import scrape_from_hidemn

__all__ = [
    'scrape_from_spysone',
    'scrape_from_openproxylist',
    'scrape_from_hidemn',
]
