import os
import time
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import threading
import logging
import asyncio
import json
from data_logger import log_interaction, save_to_excel
from sports_scraper import scrape_sport5, scrape_sport1, scrape_one
import signal
from contextlib import contextmanager

# הגדרת לוגינג
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

logger.debug("Checking TELEGRAM_TOKEN...")
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("שגיאה: TELEGRAM_TOKEN לא מוגדר! הבוט לא ירוץ.")
    exit(1)
logger.info(f"TELEGRAM_TOKEN found: {TOKEN[:5]}... (shortened for security)")

# הגדרת API של Apify עם אימות טוקן
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
if not APIFY_API_TOKEN:
    logger.error("שגיאה: APIFY_API_TOKEN לא מוגדר! אנא הגדר אותו ב-Render תחת Environment Variables עם הטוקן האמיתי מ-Apify Console.")
    exit(1)
logger.debug(f"APIFY_API_TOKEN length: {len(APIFY_API_TOKEN)} characters (not showing full token for security)")
APIFY_ACTOR_ID = "XjjDkeadhnlDBTU6i"
APIFY_API_URL = "https://api.apify.com/v2"

NEWS_SITES = {
    'ynet': 'https://www.ynet.co.il/news',
    'arutz7': 'https://www.inn.co.il/api/NewAPI/Cat?type=10',
    'walla': 'https://news.walla.co.il/',
    'ynet_tech': 'https://www.ynet.co.il/digital/technews',
    'kan11': 'https://www.kan.org.il/umbraco/surface/NewsFlashSurface/GetNews?currentPageId=1579',
    'kan11_alt': 'https://www.kan.org.il/news-flash',
    'channel14': 'https://www.now14.co.il/feed/',
    'reshet13': 'https://13tv.co.il/_next/data/ObWGmDraUyjZLnpGtZra0/he/news/news-flash.json?all=news&all=news-flash'  # ה-URL של רשת 13
}

BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,he;q=0.8',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

@contextmanager
def timeout(seconds):
    def handler(signum, frame):
        raise TimeoutError("סקרייפינג נמשך יותר מדי זמן")
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def scrape_ynet():
    try:
        response = requests.get(NEWS_SITES['ynet'], headers=BASE_HEADERS)
        soup = BeautifulSoup(response.text, 'html.parser')
        return [{'title': item.text.strip(), 'link': item.find('a')['href']} for item in soup.select('div.slotTitle')[:5]]
    except Exception as e:
        logger.error(f"שגיאה ב-Ynet: {e}")
        return []

def scrape_arutz7():
    try:
        response = requests.get(NEWS_SITES['arutz7'], headers=BASE_HEADERS)
        logger.debug(f"Arutz 7 API response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        items = data.get('Items', []) if 'Items' in data else data
        return [
            {
                'time': item.get('time', item.get('itemDate', "ללא שעה")[:16].replace('T', ' ')),
                'title': item.get('title', 'ללא כותרת'),
                'link': item.get('shotedLink', item.get('link', '#'))
            } for item in items[:3]
        ]
    except Exception as e:
        logger.error(f"שגיאה בערוץ 7: {e}")
        return []

def scrape_walla():
    try:
        response = requests.get(NEWS_SITES['walla'], headers=BASE_HEADERS)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select_one('div.top-section-newsflash.no-mobile').select('a') if soup.select_one('div.top-section-newsflash.no-mobile') else []
        results = []
        for item in items:
            title = item.get_text(strip=True)
            if title in ["מבזקי חדשות", "מבזקים"]:
                continue
            if len(title) > 5 and title[2] == ':':
                title = title[:5] + ": " + title[5:]
            link = item['href']
            if not link.startswith('http'):
                link = f"https://news.walla.co.il{link}"
            results.append({'title': title, 'link': link})
        return results[:3]
    except Exception as e:
        logger.error(f"שגיאה ב-Walla: {e}")
        return []

def scrape_ynet_tech():
    try:
        response = requests.get(NEWS_SITES['ynet_tech'], headers=BASE_HEADERS, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('div.slotView')[:3]
        results = []
        for idx, article in enumerate(articles):
            title_tag = article.select_one('div.slotTitle a')
            link_tag = title_tag
            time_tag = article.select_one('span.dateView')
            title = title_tag.get_text(strip=True) if title_tag else 'ללא כותרת'
            link = link_tag['href'] if link_tag else '#'
            article_time = time_tag.get_text(strip=True) if time_tag else 'ללא שעה'
            if not link.startswith('http'):
                link = f"https://www.ynet.co.il{link}"
            results.append({'time': article_time, 'title': title, 'link': link})
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג Ynet Tech: {str(e)}")
        return [], f"שגיאה לא ידועה: {str(e)}"

def scrape_kan11():
    try:
        with timeout(60):  # מגביל ל-60 שניות
            logger.debug("Starting Kan 11 scrape")
            response = requests.get(NEWS_SITES['kan11'], headers=BASE_HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('div.accordion-item.f-news__item')[:3]
            if not items:
                logger.warning("לא נמצאו מבזקים ב-URL הראשי, מנסה URL חלופי")
                response = requests.get(NEWS_SITES['kan11_alt'], headers=BASE_HEADERS, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('div.accordion-item.f-news__item')[:3]
                if not items:
                    logger.debug(f"Kan 11 HTML: {response.text[:500]}")
                    return [], "לא נמצאו מבזקים ב-HTML"
            results = []
            for item in items:
                time_tag = item.select_one('div.time')
                title_tag = item.select_one('div.d-flex.flex-grow-1 span')
                link_tag = item.select_one('a.card-link')
                article_time = time_tag.get_text(strip=True) if time_tag else 'ללא שעה'
                title = title_tag.get_text(strip=True) if title_tag else 'ללא כותרת'
                link = link_tag['href'] if link_tag else None
                if link and not link.startswith('http'):
                    link = f"https://www.kan.org.il{link}"
                results.append({'time': article_time, 'title': title, 'link': link})
            logger.info(f"סקריפינג כאן 11 הצליח: {len(results)} מבזקים")
            return results, None
    except TimeoutError:
        logger.error("סקרייפינג כאן 11 נכשל: לקח יותר מ-60 שניות")
        return [], "לקח יותר מדי זמן"
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג כאן 11: {str(e)}")
        return [], f"שגיאה בסקריפינג: {str(e)}"

def scrape_reshet13():
    try:
        # שליחת בקשה ל-URL
        response = requests.get(NEWS_SITES['reshet13'], headers=BASE_HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # הדפסת ה-JSON המלא ללוגים
        logger.info(f"תגובה מלאה מרשת 13:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
        
        # שליפת המבזקים
        page_props = data.get('pageProps', {})
        if not page_props:
            logger.error("לא נמצא 'pageProps' ב-JSON של רשת 13")
            return [], "לא נמצא 'pageProps' בנתונים"
        
        content = page_props.get('Content', {})
        if not content:
            logger.error("לא נמצא 'Content' ב-JSON של רשת 13")
            return [], "לא נמצא 'Content' בנתונים"
        
        page_grid = content.get('PageGrid', [])
        if not page_grid or not isinstance(page_grid, list) or len(page_grid) == 0:
            logger.error("לא נמצא 'PageGrid' תקף ב-JSON של רשת 13")
            return [], "לא נמצא 'PageGrid' תקף בנתונים"
        
        news_flash_arr = page_grid[0].get('newsFlashArr', [])
        if not news_flash_arr:
            logger.error("לא נמצא 'newsFlashArr' ב-JSON של רשת 13")
            return [], "לא נמצא 'newsFlashArr' בנתונים"
        
        # עיבוד 3 המבזקים האחרונים
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

async def run_apify_actor():
    logger.debug("Running Apify Actor...")
    max_retries = 3
    retry_delay = 5  # עיכוב של 5 שניות בין ניסיונות

    for attempt in range(max_retries):
        try:
            url = f"{APIFY_API_URL}/acts/{APIFY_ACTOR_ID}/runs?limit=2&desc=1"  # מבקש 2 ריצות
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
            for item in dataset_items[:3]:  # עד 3 פריטים
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
                            pub_date = pub_date.split('+')[0].strip()
                            pub_date = ' '.join(pub_date.split()[1:4])
                        except Exception as e:
                            logger.debug(f"Error formatting pubDate for item '{title}': {e}")
                    else:
                        pub_date = 'ללא שעה'
                    
                    if pub_date == 'ללא שעה':
                        date_tag = rss_item.find('dc:date')
                        pub_date = date_tag.string.strip() if date_tag and date_tag.string else 'ללא שעה'
                        if pub_date != 'ללא שעה':
                            try:
                                pub_date = pub_date.split('T')[0] + ' ' + pub_date.split('T')[1].split('+')[0]
                            except Exception as e:
                                logger.debug(f"Error formatting dc:date for item '{title}' {e}")
                    
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat = await context.bot.get_chat(user_id)
    username = chat.username
    logger.debug(f"User {user_id} sent /start, username: {username}")
    log_interaction(user_id, "/start", username)
    await update.message.reply_text("ברוך הבא! השתמש ב-/latest למבזקים.")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat = await context.bot.get_chat(user_id)
    username = chat.username
    logger.debug(f"User {user_id} sent /download, username: {username}")
    log_interaction(user_id, "/download", username)
    SECRET_PASSWORD = os.getenv("DOWNLOAD_PASSWORD")

    if not SECRET_PASSWORD:
        await update.message.reply_text("שגיאה: הסיסמה לא מוגדרת בשרת!")
        return
    
    if not context.args or context.args[0] != SECRET_PASSWORD:
        await update.message.reply_text("סיסמה שגויה! אין גישה.")
        return
    
    try:
        filename = save_to_excel()
        if not os.path.exists(filename):
            await update.message.reply_text("שגיאה: הקובץ לא נוצר!")
            return
        with open(filename, 'rb') as file:
            await update.message.reply_text("הנה הנתונים שלך!")
            await update.message.reply_document(document=file, filename="bot_usage.xlsx")
        os.remove(filename)
    except Exception as e:
        logger.error(f"שגיאה בשליחת הקובץ: {e}")
        await update.message.reply_text(f"שגיאה בהורדה: {str(e)}")

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat = await context.bot.get_chat(user_id)
    username = chat.username
    logger.debug(f"User {user_id} sent /latest, username: {username}")
    log_interaction(user_id, "/latest", username)
    await update.message.reply_text("מחפש מבזקים...")
    ynet_news = scrape_ynet()
    arutz7_news = scrape_arutz7()
    walla_news = scrape_walla()

    news = {'Ynet': ynet_news, 'ערוץ 7': arutz7_news, 'Walla': walla_news}
    message = "📰 **המבזקים האחרונים** 📰\n\n"
    for site, articles in news.items():
        message += f"**{site}:**\n"
        if articles:
            for idx, article in enumerate(articles[:3], 1):
                if 'time' in article:
                    message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
                else:
                    message += f"{idx}. [{article['title']}]({article['link']})\n"
        else:
            message += "לא ניתן לטעון כרגע\n"
        message += "\n"
    
    keyboard = [
        [InlineKeyboardButton("⚽🏀 חדשות ספורט", callback_data='sports_news')],
        [InlineKeyboardButton("💻 חדשות טכנולוגיה", callback_data='tech_news')],
        [InlineKeyboardButton("📺 חדשות מערוצי טלוויזיה", callback_data='tv_news')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def sports_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat = await context.bot.get_chat(user_id)
    username = chat.username
    logger.debug(f"User {user_id} triggered sports_news, username: {username}")
    log_interaction(user_id, "sports_news", username)
    await query.answer()
    await query.message.reply_text("מחפש מבזקי ספורט...")
    
    sport5_news, sport5_error = scrape_sport5()
    sport1_news, sport1_error = scrape_sport1()
    one_news, one_error = scrape_one()
    
    message = "**ספורט 5**\n"
    if sport5_news:
        for idx, article in enumerate(sport5_news[:3], 1):
            message += f"{idx}. [{article['title']}]({article['link']})\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {sport5_error}\n"
    
    message += "\n**ספורט 1**\n"
    if sport1_news:
        for idx, article in enumerate(sport1_news[:3], 1):
            message += f"{idx}. [{article['title']}]({article['link']})\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {sport1_error}\n"
    
    message += "\n**ONE**\n"
    if one_news:
        for idx, article in enumerate(one_news[:3], 1):
            message += f"{idx}. [{article['title']}]({article['link']})\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {one_error}\n"
    
    keyboard = [[InlineKeyboardButton("🏠 חזרה לעמוד ראשי", callback_data='latest_news')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def tech_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat = await context.bot.get_chat(user_id)
    username = chat.username
    logger.debug(f"User {user_id} triggered tech_news, username: {username}")
    log_interaction(user_id, "tech_news", username)
    await query.answer()
    await query.message.reply_text("מחפש חדשות טכנולוגיה...")
    
    ynet_tech_news, ynet_tech_error = scrape_ynet_tech()
    message = "**Ynet Tech**\n"
    if ynet_tech_news:
        for idx, article in enumerate(ynet_tech_news[:3], 1):
            message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {ynet_tech_error}\n"
    
    keyboard = [[InlineKeyboardButton("🏠 חזרה לעמוד ראשי", callback_data='latest_news')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def tv_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat = await context.bot.get_chat(user_id)
    username = chat.username
    logger.debug(f"User {user_id} triggered tv_news, username: {username}")
    log_interaction(user_id, "tv_news", username)
    await query.answer()
    await query.message.reply_text("מביא חדשות מערוצי טלוויזיה...")
    
    kan11_news, kan11_error = scrape_kan11()
    channel14_news, channel14_error = await run_apify_actor()  # שואב את תוצאות הריצה האחרונה
    reshet13_news, reshet13_error = scrape_reshet13()  # הוספת רשת 13
    
    message = "**חדשות מערוצי טלוויזיה**\n\n**כאן 11**:\n"
    if kan11_news:
        for idx, article in enumerate(kan11_news[:3], 1):
            if article['link']:
                message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
            else:
                message += f"{idx}. {article['time']} - {article['title']}\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {kan11_error}\n"
    
    message += "\n**עכשיו 14**:\n"
    if channel14_news:
        for idx, article in enumerate(channel14_news[:3], 1):
            if article['link']:
                message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
            else:
                message += f"{idx}. {article['time']} - {article['title']}\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {channel14_error}\n"
    
    message += "\n**קשת 12**: (הערה: הפונקציה עדיין בבנייה)\n"
    
    message += "\n**רשת 13**:\n"
    if reshet13_news:
        for idx, article in enumerate(reshet13_news[:3], 1):
            if article['link']:
                message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
            else:
                message += f"{idx}. {article['time']} - {article['title']}\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {reshet13_error}\n"
    
    keyboard = [[InlineKeyboardButton("🏠 חזרה לעמוד ראשי", callback_data='latest_news')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def latest_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat = await context.bot.get_chat(user_id)
    username = chat.username
    logger.debug(f"User {user_id} triggered latest_news, username: {username}")
    log_interaction(user_id, "latest_news", username)
    await query.answer()
    
    ynet_news = scrape_ynet()
    arutz7_news = scrape_arutz7()
    walla_news = scrape_walla()

    news = {'Ynet': ynet_news, 'ערוץ 7': arutz7_news, 'Walla': walla_news}
    message = "📰 **המבזקים האחרונים** 📰\n\n"
    for site, articles in news.items():
        message += f"**{site}:**\n"
        if articles:
            for idx, article in enumerate(articles[:3], 1):
                if 'time' in article:
                    message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
                else:
                    message += f"{idx}. [{article['title']}]({article['link']})\n"
        else:
            message += "לא ניתן לטעון כרגע\n"
        message += "\n"
    
    keyboard = [
        [InlineKeyboardButton("⚽🏀 חדשות ספורט", callback_data='sports_news')],
        [InlineKeyboardButton("💻 חדשות טכנולוגיה", callback_data='tech_news')],
        [InlineKeyboardButton("📺 חדשות מערוצי טלוויזיה", callback_data='tv_news')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

@app.route('/')
def home():
    logger.debug("Flask server accessed")
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    logger.info("Initializing bot...")
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("latest", latest))
    bot_app.add_handler(CommandHandler("download", download))
    bot_app.add_handler(CallbackQueryHandler(sports_news, pattern='sports_news'))
    bot_app.add_handler(CallbackQueryHandler(tech_news, pattern='tech_news'))
    bot_app.add_handler(CallbackQueryHandler(tv_news, pattern='tv_news'))
    bot_app.add_handler(CallbackQueryHandler(latest_news, pattern='latest_news'))

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    logger.info("Starting bot polling in main thread...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot polling started successfully")