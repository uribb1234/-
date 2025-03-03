import os
import cloudscraper
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import threading
import logging
from data_logger import log_interaction, save_to_excel

# הגדרת לוגים לדיבאג
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# הגדרות
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("שגיאה: הטוקן לא מוגדר!")
    exit(1)

NEWS_SITES = {
    'ynet': 'https://www.ynet.co.il/news',
    'arutz7': 'https://www.inn.co.il/api/NewAPI/Cat?type=10',
    'walla': 'https://news.walla.co.il/',
    'sport5': 'https://m.sport5.co.il/',
    'sport1': 'https://sport1.maariv.co.il/',
    'one': 'https://m.one.co.il/mobile/'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124'
}

# יצירת אפליקציית Flask דמה
app = Flask(__name__)

# יצירת אפליקציית Telegram
bot_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    logger.info(f"User {user_id} sent /start, username: {username}")  # לוג פשוט
    log_interaction(user_id, "/start", username)
    await update.message.reply_text("ברוך הבא! השתמש ב-/latest למבזקים.")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    logger.info(f"User {user_id} sent /download, username: {username}")  # לוג פשוט
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
            await update.message.reply_document(document=file, filename="bot_usage.xlsx")
        await update.message.reply_text("הנה הנתונים שלך!")
        os.remove(filename)
    except Exception as e:
        logger.error(f"שגיאה בשליחת הקובץ: {e}")
        await update.message.reply_text(f"שגיאה בהורדה: {str(e)}")

def scrape_ynet():
    try:
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(NEWS_SITES['ynet'], headers=HEADERS).text, 'html.parser')
        return [{'title': item.text.strip(), 'link': item.find('a')['href']} for item in soup.select('div.slotTitle')[:5]]
    except Exception as e:
        logger.error(f"שגיאה ב-Ynet: {e}")
        return []

def scrape_arutz7():
    try:
        response = requests.get(NEWS_SITES['arutz7'], headers=HEADERS)
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
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(NEWS_SITES['walla'], headers=HEADERS).text, 'html.parser')
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

def scrape_sport5():
    try:
        url = 'https://m.sport5.co.il/'
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(url, headers=HEADERS).text, 'html.parser')
        
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
        
        logger.info(f"סקריפינג ספורט 5 הצליח: {len(results)} כתבות נשלפו")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג ספורט 5: {e}")
        return [], f"שגיאה לא ידועה: {str(e)}"

def scrape_sport1():
    try:
        url = 'https://sport1.maariv.co.il/'
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(url, headers=HEADERS).text, 'html.parser')
        
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
        
        logger.info(f"סקריפינג ספורט 1 הצליח: {len(results)} כתבות נשלפו")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג ספורט 1: {e}")
        return [], f"שגיאה לא ידועה: {str(e)}"

def scrape_one():
    try:
        url = 'https://m.one.co.il/mobile/'
        scraper = cloudscraper.create_scraper()
        soup = BeautifulSoup(scraper.get(url, headers=HEADERS).text, 'html.parser')
        
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
        
        logger.info(f"סקריפינג ONE הצליח: {len(results)} כתבות נשלפו")
        return results, None
    except Exception as e:
        logger.error(f"שגיאה בסקריפינג ONE: {e}")
        return [], f"שגיאה לא ידועה: {str(e)}"

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    logger.info(f"User {user_id} sent /latest, username: {username}")  # לוג פשוט
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
    
    keyboard = [[InlineKeyboardButton("⚽🏀 קבלת מבזקי ספורט", callback_data='sports_news')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def sports_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    username = query.from_user.username
    logger.info(f"User {user_id} triggered sports_news, username: {username}")  # לוג פשוט
    log_interaction(user_id, "sports_news", username)
    await query.answer()
    
    await query.message.reply_text("מחפש מבזקי ספורט...")
    
    sport5_news, sport5_error = scrape_sport5()
    sport1_news, sport1_error = scrape_sport1()
    one_news, one_error = scrape_one()
    
    message = "**ספורט 5**\n"
    if sport5_news:
        for idx, article in enumerate(sport5_news[:3], 1):
            if 'time' in article:
                message += f"{idx}. {article['time']} - [{article['title']}]({article['link']})\n"
            else:
                message += f"{idx}. [{article['title']}]({article['link']})\n"
    else:
        message += "לא ניתן למצוא מבזקים\n"
        if sport5_error:
            message += f"**פרטי השגיאה:** {sport5_error}\n"
    
    message += "\n**ספורט 1**\n"
    if sport1_news:
        for idx, article in enumerate(sport1_news[:3], 1):
            if 'time' in article:
                message += f"{idx}. {article['time']} - [{article['title']}]({article['link']})\n"
            else:
                message += f"{idx}. [{article['title']}]({article['link']})\n"
    else:
        message += "לא ניתן למצוא מבזקים\n"
        if sport1_error:
            message += f"**פרטי השגיאה:** {sport1_error}\n"
    
    message += "\n**ONE**\n"
    if one_news:
        for idx, article in enumerate(one_news[:3], 1):
            message += f"{idx}. [{article['title']}]({article['link']})\n"
    else:
        message += "לא ניתן למצוא מבזקים\n"
        if one_error:
            message += f"**פרטי השגיאה:** {one_error}\n"
    
    keyboard = [[InlineKeyboardButton("🏠 חזרה לעמוד ראשי", callback_data='latest_news')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

async def latest_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    username = query.from_user.username
    logger.info(f"User {user_id} triggered latest_news, username: {username}")  # לוג פשוט
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
    
    keyboard = [[InlineKeyboardButton("⚽🏀 קבלת מבזקי ספורט", callback_data='sports_news')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=reply_markup)

# שרת Flask דמה שמקשיב לפורט
@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    logger.info("מתחיל את הבוט עם Polling ושרת דמה...")
    
    # הגדרת המטפלים
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("latest", latest))
    bot_app.add_handler(CommandHandler("download", download))
    bot_app.add_handler(CallbackQueryHandler(sports_news, pattern='sports_news'))
    bot_app.add_handler(CallbackQueryHandler(latest_news, pattern='latest_news'))

    # הרצת Flask בשרשור נפרד
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # איתחול והרצת Polling
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)