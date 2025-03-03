import os
import cloudscraper
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import threading
import logging

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
    'sport5': 'https://m.sport5.co.il/'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124'
}

# יצירת אפליקציית Flask
app = Flask(__name__)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ברוך הבא! השתמש ב-/latest למבזקים.")

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

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await query.answer()
    
    await query.message.reply_text("מחפש מבזקי ספורט... (הפונקציה עדיין בפיתוח, יתכנו תקלות)")
    
    sport5_news, error_message = scrape_sport5()
    
    message = "🏀⚽ **מבזקי ספורט אחרונים - ספורט 5** 🏀⚽\n\n"
    if sport5_news:
        for idx, article in enumerate(sport5_news[:3], 1):
            if 'time' in article:
                message += f"{idx}. [{article['time']} - {article['title']}]({article['link']})\n"
            else:
                message += f"{idx}. [{article['title']}]({article['link']})\n"
    else:
        message += "לא ניתן למצוא מבזקים\n"
        if error_message:
            message += f"**פרטי השגיאה:** {error_message}"
    
    await query.message.reply_text(text=message, parse_mode='Markdown', disable_web_page_preview=True)

@app.route('/')
def home():
    return "Bot is alive!"

if __name__ == "__main__":
    logger.info("מתחיל את השרת והבוט...")
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info(f"מנסה להתחבר לטלגרם עם הטוקן: {TOKEN[:10]}...")
    try:
        bot_app = Application.builder().token(TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CommandHandler("latest", latest))
        bot_app.add_handler(CallbackQueryHandler(sports_news, pattern='sports_news'))
        logger.info("התחברתי לטלגרם בהצלחה!")
        bot_app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"שגיאה בהרצת הבוט: {e}")