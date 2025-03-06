import os
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

# ... (שאר הפונקציות נשארות אותו דבר: start, download, latest, scrape_ynet, scrape_arutz7, scrape_walla, scrape_ynet_tech)

async def scrape_kan11():
    try:
        logger.debug("Starting Kan 11 scrape with Playwright")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(NEWS_SITES['kan11'], wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)  # ממתין לפתרון Cloudflare
            content = await page.content()
            logger.debug(f"Kan 11 HTML content: {content[:500]}...")  # לוג של 500 תווים ראשונים
            await browser.close()
        
        soup = BeautifulSoup(content, 'html.parser')
        items = soup.select('div.accordion-item.f-news__item')  # בדוק אם הסלקטור תואם
        
        if not items:
            logger.warning("לא נמצאו מבזקים ב-HTML של כאן 11")
            return [], "לא נמצאו מבזקים ב-HTML"
        
        results = []
        for item in items[:3]:
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
            logger.debug(f"Channel 14 content: {content[:500]}...")  # לוג של 500 תווים ראשונים
            await browser.close()
        
        if "<html" in content.lower():
            logger.warning("Channel 14 returned HTML instead of RSS")
            return [], "התקבל HTML במקום RSS, כנראה חסימה של Cloudflare"
        
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

# ... (שאר הפונקציות נשארות אותו דבר: sports_news, tech_news, tv_news, latest_news, home, run_flask, if __name__ == "__main__")
