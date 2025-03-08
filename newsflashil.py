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

# הגדרת API של Apify
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
logger.debug(f"APIFY_API_TOKEN value: {APIFY_API_TOKEN}")  # לוג זמני לבדיקה
if not APIFY_API_TOKEN:
    logger.error("שגיאה: APIFY_API_TOKEN לא מוגדר! לא ניתן להפעיל את ה-Actor.")
    exit(1)
APIFY_ACTOR_ID = "your-username~now14-telegram-bot"  # החלף עם ה-ID שלך
APIFY_API_URL = "https://api.apify.com/v2"

NEWS_SITES = {
    'ynet': 'https://www.ynet.co.il/news',
    'arutz7': 'https://www.inn.co.il/api/NewAPI/Cat?type=10',
    'walla': 'https://news.walla.co.il/',
    'ynet_tech': 'https://www.ynet.co.il/digital/technews',
    'kan11': 'https://www.kan.org.il/umbraco/surface/NewsFlashSurface/GetNews?currentPageId=1579',
    'kan11_alt': 'https://www.kan.org.il/news-flash',
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

# פונקציה להפעלת ה-Actor של Apify ולשליפת התוצאות
async def run_apify_actor():
    try:
        # הפעל את ה-Actor
        logger.debug("Starting Apify Actor run...")
        run_response = requests.post(
            f"{APIFY_API_URL}/acts/{APIFY_ACTOR_ID}/runs",
            headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"},
            json={"timeout": 60}
        )
        run_response.raise_for_status()
        run_data = run_response.json()
        run_id = run_data['data']['id']
        logger.debug(f"Actor run started with ID: {run_id}")

        # המתן עד שהריצה תסתיים
        max_wait_time = 120  # המתנה מקסימלית של 120 שניות
        wait_time = 0
        while wait_time < max_wait_time:
            status_response = requests.get(
                f"{APIFY_API_URL}/acts/{APIFY_ACTOR_ID}/runs/{run_id}",
                headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"}
            )
            status_response.raise_for_status()
            status_data = status_response.json()
            status = status_data['data']['status']
            if status in ['SUCCEEDED', 'FAILED', 'TIMED-OUT']:
                break
            time.sleep(5)
            wait_time += 5

        if status != 'SUCCEEDED':
            logger.error(f"Actor run failed with status: {status}")
            return [], f"שגיאה בהרצת ה-Actor: {status}"

        # שלוף את ה-Dataset מהריצה
        dataset_id = run_data['data']['defaultDatasetId']
        dataset_response = requests.get(
            f"{APIFY_API_URL}/datasets/{dataset_id}/items",
            headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"}
        )
        dataset_response.raise_for_status()
        dataset_items = dataset_response.json()

        if not dataset_items:
            logger.warning("לא נמצאו פריטים ב-Dataset")
            return [], "לא נמצאו מבזקים ב-Dataset"

        # עיבוד התוצאות
        results = []
        for item in dataset_items[:3]:  # עד 3 מבזקים
            content = item.get('content', '')
            soup = BeautifulSoup(content, 'xml')
            items = soup.select('item')[:3]
            for rss_item in items:
                title = rss_item.find('title').get_text(strip=True) if rss_item.find('title') else 'ללא כותרת'
                link = rss_item.find('link').get_text(strip=True) if rss_item.find('link') else None
                pub_date = rss_item.find('pubDate').get_text(strip=True) if rss_item.find('pubDate') else 'ללא שעה'
                results.append({'time': pub_date, 'title': title, 'link': link})

        logger.info(f"שאיבה מערוץ 14 דרך Apify הצליחה: {len(results)} מבזקים")
        return results, None

    except Exception as e:
        logger.error(f"שגיאה בהפעלת Apify Actor: {str(e)}")
        return [], f"שגיאה בשאיבה דרך Apify: {str(e)}"

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
    channel14_news, channel14_error = await run_apify_actor()  # מפעיל את Apify באופן אוטומטי
    
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
    message += "**רשת 13**: (הערה: הפונקציה עדיין בבנייה)\n"
    
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
