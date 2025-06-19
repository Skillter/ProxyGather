call conda activate

pip install -r requirements.txt

git clone https://github.com/sarperavci/CloudflareBypassForScraping
pip install -r CloudflareBypassForScraping/requirements.txt
type nul > CloudflareBypassForScraping/__init__.py
timeout 3

echo Installing proxyz with pip
pip install -U proxyz

echo installing mubeng with go
go install -v github.com/mubeng/mubeng@latest

echo Downloading ProxyScraper.py
curl -o scrapers/ProxyScraper-original.py https://raw.githubusercontent.com/SIDDHU123M/Ultimate-Proxy-Scraper/refs/heads/main/ProxyScraper.py

@REM git clone https://github.com/chill117/proxy-lists.git
@REM cd proxy-lists
@REM npm install

timeout 5