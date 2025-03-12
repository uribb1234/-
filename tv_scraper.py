import os
import time
import requests
import json
from bs4 import BeautifulSoup
import logging
import asyncio

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_ACTOR_ID = "XjjDkeadhnlDBTU6i"
APIFY_API_URL = "https://api.apify.com/v2"

TV_SITES = {
    'keshet12': 'https://www.mako.co.il/news-dailynews',
    'reshet13': 'https://13tv.co.il/_next/data/ObWGmDraUyjZLnpGtZra0/he/news/news-flash.json?all=news&all=news-flash',
    'channel14': 'https://www.now14.co.il/feed/'
}

BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def scrape_reshet13():
    try:
        url = TV_SITES['reshet13']
        response = requests.get(url, headers=BASE_HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"תגובה מלאה מרשת 13:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
        
        page_props = data.get('pageProps', {})
        if not page_props:
            logger.error(f"לא נמצא 'pageProps' ב-JSON של רשת 13:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
            return [], "לא נמצא 'pageProps' בנתונים"
        
        page = page_props.get('page', {})
        if not page:
            logger.error(f"לא נמצא 'page' ב-pageProps של רשת 13:\n{json.dumps(page_props, ensure_ascii=False, indent=2)}")
            return [], "לא נמצא 'page' בנתונים"
        
        content = page.get('Content', {})
        if not content:
            logger.error(f"לא נמצא 'Content' ב-page של רשת 13:\n{json.dumps(page, ensure_ascii=False, indent=2)}")
            return [], "לא נמצא 'Content' בנתונים"
        
        page_grid = content.get('PageGrid', [])
        if not page_grid or not isinstance(page_grid, list) or len(page_grid) == 0:
            logger.error(f"לא נמצא 'PageGrid' תקף ב-Content של רשת 13:\n{json.dumps(content, ensure_ascii=False, indent=2)}")
            return [], "לא נמצא 'PageGrid' תקף בנתונים"
        
        news_flash_arr = page_grid[0].get('newsFlashArr', [])
        if not news_flash_arr:
            news_flash_arr = page_props.get('newsFlashArr', [])
            if not news_flash_arr:
                logger.error(f"לא נמצא 'newsFlashArr' ב-PageGrid[0] או ב-pageProps:\n{json.dumps(page_grid[0], ensure_ascii=False, indent=2)}")
                return [], "לא נמצא 'newsFlashArr' בנתונים"
        
        results = []
        for item in news_flash_arr[:3]:
            title = item.get('text', 'ללא כותרת')
            link = item.get('link', '')
            if link and not link.startswith('http'):
                link = f"https://13tv.co.il{link}"
            time_str = item.get('time', 'ללא שעה')
            try:
                time_formatted = time_str.replace('-', '/')[2:10] + ' ' + time_str[11:16]
            except:
                time_formatted = 'ללא שעה'
            results.append({'time': time_formatted, 'title': title, 'link': link})
        
        logger.info(f"סקריפינג רשת 13 הצליח: {len(results)} מבזקים")
        return results, None
    except requests.exceptions.RequestException as e:
        logger.error(f"שגיאה בבקשה לרשת 13: {str(e)}")
        return [], f"שגיאה בבקשה: {str(e)}"
    except ValueError as e:
        logger.error(f"שגיאה בפענוח JSON מרשת 13: {str(e)}")
        return [], f"שגיאה בפענוח JSON: {str(e)}"
    except Exception as e:
        logger.error(f"שגיאה לא צפויה בסקריפינג רשת 13: {str(e)}")
        return [], f"שגיאה לא צפויה: {str(e)}"

def scrape_keshet12():
    try:
        response = requests.get(TV_SITES['keshet12'], headers=BASE_HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('ul.grid-ordering.mainItem6 > li')[:3]
        results = []
        for item in items:
            title_tag = item.select_one('p strong a')
            link_tag = title_tag
            time_tag = item.select('small span')[1] if len(item.select('small span')) > 1 else None
            title = title_tag.get_text(strip=True) if title_tag else 'ללא כותרת'
            link = link_tag['href'] if link_tag else '#'
            if not link.startswith('http'):
                link = f"https://www.mako.co.il{link}"
            article_time = time_tag.get_text(strip=True) if time_tag else 'ללא שעה'
            results.append({'time': article_time, 'title': title, 'link': link})
        logger.info(f"סקריפינג קשת 12 הצליח: {len(results)} כתבות")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג קשת 12: {str(e)}")
        return [], f"שגיאה בסקריפינג: {str(e)}"

async def run_apify_actor():
    logger.debug("Running Apify Actor...")
    max_retries = 3
    retry_delay = 5
    months_hebrew = {
        'Jan': 'ינואר', 'Feb': 'פברואר', 'Mar': 'מרץ', 'Apr': 'אפריל',
        'May': 'מאי', 'Jun': 'יוני', 'Jul': 'יולי', 'Aug': 'אוגוסט',
        'Sep': 'ספטמבר', 'Oct': 'אוקטובר', 'Nov': 'נובמבר', 'Dec': 'דצמבר'
    }

    for attempt in range(max_retries):
        try:
            url = f"{APIFY_API_URL}/acts/{APIFY_ACTOR_ID}/runs?limit=2&desc=1"
            headers = {
                "Authorization": f"Bearer {APIFY_API_TOKEN}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to fetch latest Apify Actor run: {response.status_code} - {response.text}")
                response.raise_for_status()
            run_data = response.json()
            
            if not run_data.get('data', {}).get('items'):
                logger.error("No runs found for this Actor.")
                return [], "לא נמצאו ריצות עבור ה-Actor הזה. ודא שה-Actor מוגדר לרוץ כל שעה ב-Apify."

            runs = run_data['data']['items']
            latest_run = runs[0]
            run_id = latest_run['id']
            status = latest_run['status']
            logger.debug(f"Latest run ID: {run_id}, Status: {status}")

            if status == 'RUNNING' and len(runs) > 1:
                logger.warning("Latest run is RUNNING, checking previous run...")
                previous_run = runs[1]
                if previous_run['status'] == 'SUCCEEDED':
                    latest_run = previous_run
                    status = 'SUCCEEDED'
                    logger.info("Using previous successful run.")
                else:
                    if attempt < max_retries - 1:
                        logger.info(f"Waiting {retry_delay} seconds before retrying...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error("All runs failed or still running after retries.")
                        return [], "כל הריצות נכשלו או עדיין רצות."

            if status != 'SUCCEEDED':
                logger.error(f"Latest Actor run did not succeed. Status: {status}")
                return [], f"הריצה האחרונה של ה-Actor לא הצליחה. סטטוס: {status}"

            dataset_id = latest_run['defaultDatasetId']
            if not dataset_id:
                logger.error("No dataset ID found in the latest run.")
                return [], "לא נמצא Dataset ID עבור הריצה האחרונה."

            dataset_url = f"{APIFY_API_URL}/datasets/{dataset_id}/items"
            dataset_response = requests.get(dataset_url, headers=headers, timeout=30)
            if dataset_response.status_code != 200:
                logger.error(f"Failed to fetch dataset items: {dataset_response.status_code} - {dataset_response.text}")
                dataset_response.raise_for_status()
            
            dataset_items = dataset_response.json()
            logger.debug(f"Dataset items: {json.dumps(dataset_items, ensure_ascii=False)[:2000]}... (truncated)")
            if not dataset_items:
                logger.warning("לא נמצאו פריטים ב-Dataset")
                return [], "לא נמצאו מבזקים ב-Dataset של הריצה האחרונה"

            results = []
            for item in dataset_items[:3]:
                content = item.get('content', '')
                logger.debug(f"Processing dataset item content (raw): {content[:2000]}... (truncated)")
                if not content:
                    logger.warning("Content is empty for this item")
                    continue
                
                soup = BeautifulSoup(content, 'html.parser')
                pre_content = soup.find('pre').text if soup.find('pre') else content
                logger.debug(f"Cleaned pre content: {pre_content[:2000]}... (truncated)")
                
                rss_soup = BeautifulSoup(pre_content, 'lxml')
                items = rss_soup.select('item')[:3]
                if not items:
                    logger.warning("לא נמצאו תגיות <item> ב-RSS")
                    all_tags = [tag.name for tag in rss_soup.find_all()]
                    logger.debug(f"כל התגיות שנמצאו ב-RSS: {all_tags}")
                    logger.debug(f"Full RSS structure: {rss_soup.prettify()[:2000]}... (truncated)")
                    continue

                for rss_item in items:
                    title = rss_item.find('title')
                    title = title.get_text(strip=True) if title else 'ללא כותרת'
                    
                    link = None
                    link_tag = rss_item.find('link')
                    if link_tag and link_tag.string:
                        link = link_tag.string.strip()
                    logger.debug(f"Extracted link for item '{title}': {link}")
                    
                    if not link:
                        guid_tag = rss_item.find('guid')
                        if guid_tag and guid_tag.string:
                            link = guid_tag.string.strip()
                        logger.debug(f"Extracted link from guid for item '{title}': {link}")
                    
                    pub_date = rss_item.find('pubdate')
                    if pub_date and pub_date.string:
                        pub_date = pub_date.string.strip()
                        try:
                            parts = pub_date.split()
                            day = parts[1]
                            month = months_hebrew.get(parts[2], parts[2])
                            year = parts[3]
                            pub_date = f"{day} {month} {year}"
                        except Exception as e:
                            logger.debug(f"Error formatting pubDate for item '{title}': {e}")
                            pub_date = 'ללא שעה'
                    else:
                        pub_date = 'ללא שעה'
                    
                    if pub_date == 'ללא שעה':
                        date_tag = rss_item.find('dc:date')
                        pub_date = date_tag.string.strip() if date_tag and date_tag.string else 'ללא שעה'
                        if pub_date != 'ללא שעה':
                            try:
                                date_parts = pub_date.split('T')[0].split('-')
                                year, month, day = date_parts
                                month = months_hebrew.get(month, month)
                                pub_date = f"{day} {month} {year}"
                            except Exception as e:
                                logger.debug(f"Error formatting dc:date for item '{title}': {e}")
                                pub_date = 'ללא שעה'
                    
                    results.append({'time': pub_date, 'title': title, 'link': link})

            if not results:
                logger.warning("לא נמצאו מבזקים תקינים לאחר עיבוד")
                return [], "לא נמצאו מבזקים תקינים לאחר עיבוד"

            logger.info(f"שאיבה מערוץ 14 דרך Apify הצליחה: {len(results)} מבזקים")
            return results, None

        except Exception as e:
            logger.error(f"שגיאה בשאיבת תוצאות ה-Actor מ-Apify: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                continue
            return [], f"שגיאה בשאיבה דרך Apify לאחר {max_retries} ניסיונות: {str(e)}"
