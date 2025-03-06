import cloudscraper
from bs4 import BeautifulSoup
import logging

# הגדרת לוגים ברמת DEBUG
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.google.com/'
}

def scrape_sport5():
    try:
        url = 'https://m.sport5.co.il/'
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(url, headers=BASE_HEADERS).text, 'html.parser')
        
        articles = soup.select('nav.posts-list.posts-list-articles ul li')
        
        results = []
        for item in articles[:3]:
            link_tag = item.find('a', class_='item')
            title_tag = item.find('h2', class_='post-title')
            time_tag = item.find('em', class_='time')
            
            title = title_tag.get_text(strip=True) if title_tag else 'ללא כותרת'
            link = link_tag['href'] if link_tag else '#'
            time = time_tag.get_text(strip=True) if time_tag else 'ללא שעה'
            
            if link and not link.startswith('http'):
                link = f"https://m.sport5.co.il{link}"
            
            results.append({
                'time': time,
                'title': title,
                'link': link
            })
        
        logger.debug(f"סקריפינג ספורט 5 הצליח: {len(results)} כתבות נשלפו")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג ספורט 5: {e}")
        return [], f"שגיאה לא ידועה: {str(e)}"

def scrape_sport1():
    try:
        url = 'https://sport1.maariv.co.il/'
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(url, headers=BASE_HEADERS).text, 'html.parser')
        
        articles = soup.select('div.hot-news-container article.article-card')
        
        results = []
        for item in articles[:3]:
            link_tag = item.find_parent('a', class_='image-wrapper')
            title_tag = item.find('h3', class_='article-card-title')
            time_tag = item.find('time', class_='entry-date')
            
            title = title_tag.get_text(strip=True) if title_tag else 'ללא כותרת'
            link = link_tag['href'] if link_tag else '#'
            time = time_tag.get_text(strip=True) if time_tag else 'ללא שעה'
            
            if link and not link.startswith('http'):
                link = f"https://sport1.maariv.co.il{link}"
            
            results.append({
                'time': time,
                'title': title,
                'link': link
            })
        
        logger.debug(f"סקריפינג ספורט 1 הצליח: {len(results)} כתבות נשלפו")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג ספורט 1: {e}")
        return [], f"שגיאה לא ידועה: {str(e)}"

def scrape_one():
    try:
        url = 'https://m.one.co.il/mobile/'
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(url, headers=BASE_HEADERS).text, 'html.parser')
        
        articles = soup.select('a.mobile-hp-article-plain')
        
        results = []
        for item in articles[:3]:
            link_tag = item
            title_tag = item.find('h1')
            time = 'ללא שעה'
            
            title = title_tag.get_text(strip=True) if title_tag else 'ללא כותרת'
            link = link_tag['href'] if link_tag else '#'
            
            if link and not link.startswith('http'):
                link = f"https://m.one.co.il{link}"
            
            results.append({
                'time': time,
                'title': title,
                'link': link
            })
        
        logger.debug(f"סקריפינג ONE הצליח: {len(results)} כתבות נשלפו")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג ONE: {e}")
        return [], f"שגיאה לא ידועה: {str(e)}"
