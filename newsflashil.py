import os
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import threading
import logging
import random
import time
from data_logger import log_interaction, save_to_excel
from sports_scraper import scrape_sport5, scrape_sport1, scrape_one
import feedparser
from playwright.async_api import async_playwright

# הגדרת לוגינג עם כתיבה לקובץ וקונסולה
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("שגיאה: הטוקן לא מוגדר!")
    exit(1)

NEWS_SITES = {
    'ynet': 'https://www.ynet.co.il/news',
    'arutz7': 'https://www.inn.co.il/api/NewAPI/Cat?type=10',
    'walla': 'https://news.walla.co.il/',
    'ynet_tech': 'https://www.ynet.co.il/digital/technews',
    'kan11': 'https://www.kan.org.il/umbraco/surface/NewsFlashSurface/GetNews?currentPageId=1579',
    'channel14': 'https://www.now14.co.il/feed/'
}

BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.google.com/'
}

app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

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
async def scrape_kan11():
    try:
        logger.debug("Starting Kan 11 scrape with Playwright")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(NEWS_SITES['kan11'], wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)  # ממתין לפתרון Cloudflare
            content = await page.content()
            await browser.close()
        
        soup = BeautifulSoup(content, 'html.parser')
        items = soup.select('div.accordion-item.f-news__item')[:3]
        
        if not items:
            logger.warning("לא נמצאו מבזקים ב-HTML של כאן 11")
            return [], "לא נמצאו מבזקים ב-HTML"
        
        results = []
        for item in items:
            time_tag = item.select_one('div.time')
            title_tag = item.select_one('div.d-flex.flex-grow-1 span')
            link_tag = item.select_one('a.card-link')
            article_time = time_tag.get_text(strip=True) if time_tag else 'ללא שעה'
            title = title_tag.get_text(strip=True) if title_tag else 'ללא כותרת'
            link = link_tag['href'] if link_tag else '#'
            results.append({'time': article_time, 'title': title, 'link': link})
            logger.debug(f"Kan 11 article: time='{article_time}', title='{title}', link='{link}'")
        
        logger.info(f"סקריפינג כאן 11 הצליח: {len(results)} מבזקים")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג כאן 11: {str(e)}")
        return [], f"שגיאה לא ידועה: {str(e)}"

async def scrape_channel14():
    try:
        logger.debug("Starting Channel 14 scrape with Playwright")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(NEWS_SITES['channel14'], wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)  # ממתין לפתרון Cloudflare
            content = await page.content()
            await browser.close()
        
        feed = feedparser.parse(content)
        if feed.bozo:
            logger.warning(f"Failed to parse Channel 14 RSS: {feed.bozo_exception}")
            return [], f"שגיאה בעיבוד ה-RSS: {feed.bozo_exception}"
        
        results = []
        for entry in feed.entries[:3]:
            article_time = entry.get('published', 'ללא שעה')
            title = entry.get('title', 'ללא כותרת')
            link = entry.get('link', '#')
            results.append({'time': article_time, 'title': title, 'link': link})
            logger.debug(f"Channel 14 article: time='{article_time}', title='{title}', link='{link}'")
        
        logger.info(f"סקריפינג ערוץ 14 הצליח: {len(results)} מבזקים")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג ערוץ 14: {str(e)}")
        return [], f"שגיאה לא ידועה: {str(e)}"

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
    await query.message.reply_text("מחפש חדשות מערוצי טלוויזיה...")
    
    kan11_news, kan11_error = await scrape_kan11()  # שינוי ל-await
    channel14_news, channel14_error = await scrape_channel14()  # שינוי ל-await
    
    message = "**חדשות מערוצי טלוויזיה**\n\n**כאן 11**:\n"
    if kan11_news:
        for idx, article in enumerate(kan11_news[:3], 1):
            message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {kan11_error}\n"
    
    message += "\n**עכשיו 14**:\n"
    if channel14_news:
        for idx, article in enumerate(channel14_news[:3], 1):
            message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
    else:
        message += f"לא ניתן למצוא מבזקים\n**פרטי השגיאה:** {channel14_error}\n"
    
    message += "\n**קשת 12**: (הערה: הפונקציה עדיין בבנייה)\n"
    message += "**רשת 13**: (הערה: הפונקציה עדיין בבנייה)\n"
    
    keyboard = [[InlineKeyboardButton("🏠 חזרה לעמוד ראשי", callback_data='latest_news')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup) 
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
    port = int(os.environ.get("PORT", 8080))
    logger.debug(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    logger.debug("Initializing bot with Playwright...")
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("latest", latest))
    bot_app.add_handler(CommandHandler("download", download))
    bot_app.add_handler(CallbackQueryHandler(sports_news, pattern='sports_news'))
    bot_app.add_handler(CallbackQueryHandler(tech_news, pattern='tech_news'))
    bot_app.add_handler(CallbackQueryHandler(tv_news, pattern='tv_news'))
    bot_app.add_handler(CallbackQueryHandler(latest_news, pattern='latest_news'))

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    logger.debug("Starting bot polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)
