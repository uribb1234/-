import requests
from bs4 import BeautifulSoup
import logging

# הגדרת לוגינג
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def scrape_sport5():
    logger.debug("Scraping Sport5...")
    try:
        url = "https://www.sport5.co.il/"
        response = requests.get(url, headers=BASE_HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('div.article-item')[:3]  # התאם את הסלקטור למבנה האתר
        results = []
        for article in articles:
            title_tag = article.select_one('h3')
            link_tag = article.select_one('a')
            title = title_tag.get_text(strip=True) if title_tag else "ללא כותרת"
            link = link_tag['href'] if link_tag else "#"
            if not link.startswith('http'):
                link = f"https://www.sport5.co.il{link}"
            results.append({'title': title, 'link': link})
        logger.info(f"Scraped {len(results)} items from Sport5")
        return results, None
    except Exception as e:
        logger.error(f"Error scraping Sport5: {e}")
        return [], str(e)

def scrape_sport1():
    logger.debug("Scraping Sport1...")
    try:
        url = "https://sport1.maariv.co.il/"
        response = requests.get(url, headers=BASE_HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('div.article-teaser')[:3]  # התאם את הסלקטור למבנה האתר
        results = []
        for article in articles:
            title_tag = article.select_one('h2')
            link_tag = article.select_one('a')
            title = title_tag.get_text(strip=True) if title_tag else "ללא כותרת"
            link = link_tag['href'] if link_tag else "#"
            if not link.startswith('http'):
                link = f"https://sport1.maariv.co.il{link}"
            results.append({'title': title, 'link': link})
        logger.info(f"Scraped {len(results)} items from Sport1")
        return results, None
    except Exception as e:
        logger.error(f"Error scraping Sport1: {e}")
        return [], str(e)

def scrape_one():
    logger.debug("Scraping ONE...")
    try:
        url = "https://www.one.co.il/"
        response = requests.get(url, headers=BASE_HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('div.news-item')[:3]  # התאם את הסלקטור למבנה האתר
        results = []
        for article in articles:
            title_tag = article.select_one('h3')
            link_tag = article.select_one('a')
            title = title_tag.get_text(strip=True) if title_tag else "ללא כותרת"
            link = link_tag['href'] if link_tag else "#"
            if not link.startswith('http'):
                link = f"https://www.one.co.il{link}"
            results.append({'title': title, 'link': link})
        logger.info(f"Scraped {len(results)} items from ONE")
        return results, None
    except Exception as e:
        logger.error(f"Error scraping ONE: {e}")
        return [], str(e)
