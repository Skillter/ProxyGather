call conda activate

echo Installing proxyz with pip
pip install -U proxyz

echo installing mubeng with go
go install -v github.com/mubeng/mubeng@latest

echo Downloading ProxyScraper.py
curl -o scrapers/ProxyScraper-original.py https://raw.githubusercontent.com/SIDDHU123M/Ultimate-Proxy-Scraper/refs/heads/main/ProxyScraper.py

git clone https://github.com/chill117/proxy-lists.git
cd proxy-lists
npm install

timeout 5