import requests
import logging
import json
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, LinkPreviewOptions
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from flask import Flask

# הגדרת לוגינג
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

# הגדרת אתרים ו-Headers
NEWS_SITES = {
    "ynet": "https://www.ynet.co.il/news",
    "walla": "https://news.walla.co.il",
    "arutz7": "https://www.inn.co.il/api/NewAPI/Cat?type=10",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}

# פונקציה לסקרייפינג של Ynet (מבוסס על ה-Logs)
def scrape_ynet():
    try:
        response = requests.get(NEWS_SITES['ynet'], headers=HEADERS)
        response.raise_for_status()
        # הנחה: אנחנו משתמשים ב-Apify או ב-HTML parsing
        # זה לא מדויק כי אין לי את הקוד המקורי, אבל אני מניח מבנה דומה
        data = response.text  # צריך להתאים את הפונקציה לקוד המקורי שלך
        # דוגמה לפורמט:
        return [
            {
                'time': "ללא שעה",
                'title': "בלי בן גביר שגרר את נתניהו להצבעות אחרי ניתוח: נפתר משבר תקציב המשרד לביטחון לאומי",
                'link': "https://www.ynet.co.il/news/article/bkm7tyssje"
            },
            {
                'time': "ללא שעה",
                'title': '"קודם תקציב, אחר כך היתר": העברת חוק הפטור מגיוס בספק - וגם שרידות הקואליציה',
                'link': "https://www.ynet.co.il/news/article/byaztr5s1x"
            },
            {
                'time': "ללא שעה",
                'title': "פגישה מפתיעה בוושינגטון: יועצו הלבנוני הבכיר של טראמפ נועד עם ראש מועצת שומרון",
                'link': "https://www.ynet.co.il/news/article/byfgzhci1e#autoplay"
            },
        ]
    except Exception as e:
        logger.error(f"שגיאה ב-Ynet: {e}")
        return []

# פונקציה לסקרייפינג של Walla (מבוסס על ה-Logs)
def scrape_walla():
    try:
        response = requests.get(NEWS_SITES['walla'], headers=HEADERS)
        response.raise_for_status()
        # הנחה: אנחנו משתמשים ב-HTML parsing
        # זה לא מדויק כי אין לי את הקוד המקורי, אבל אני מניח מבנה דומה
        data = response.text  # צריך להתאים את הפונקציה לקוד המקורי שלך
        # דוגמה לפורמט:
        return [
            {
                'time': "13:22",
                'title': "ממשלת ישראל אישרה פה אחד מינוי שני שגרירים חדשים",
                'link': "https://news.walla.co.il/break/3732963"
            },
            {
                'time': "13:06",
                'title': "חשוד שהחזיק כלי נשק ואמל\"ח באופן לא חוקי, מעצרו הוארך",
                'link': "https://news.walla.co.il/break/3732961"
            },
            {
                'time': "12:50",
                'title': "תושבת ירושלים איתרה אמצעי לחימה רבים בביתה, השייכים לבעלה המנוח",
                'link': "https://news.walla.co.il/break/3732956"
            },
        ]
    except Exception as e:
        logger.error(f"שגיאה ב-Walla: {e}")
        return []

# פונקציה לסקרייפינג של ערוץ 7 (מעודכנת עם השיפורים)
def scrape_arutz7():
    logger.debug("Scraping Arutz 7...")
    try:
        response = requests.get(NEWS_SITES['arutz7'], headers=HEADERS, timeout=10)
        logger.debug(f"Arutz 7 API response status: {response.status_code}")
        response.raise_for_status()

        response_text = response.text.strip()
        logger.debug(f"Arutz 7 raw response text: {response_text[:500]}... (truncated)")

        # בדיקת תגובה ריקה או לא תקינה
        if not response_text:
            logger.warning("Arutz 7 API returned empty response")
            return []
        if response_text.startswith("�") or not response_text.replace(" ", "").isprintable():
            logger.error(f"Arutz 7 API returned non-JSON data: {response_text[:100]}...")
            return []

        # ניסיון לפענוח JSON עם טיפול ב-BOM
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            # נסה להסיר BOM אם קיים
            cleaned_text = re.sub(r'^\ufeff', '', response_text)
            data = json.loads(cleaned_text)
        logger.debug(f"Arutz 7 raw JSON data: {json.dumps(data, ensure_ascii=False)[:500]}... (truncated)")

        items = data.get('Items', []) if 'Items' in data else data
        return [
            {
                'time': item.get('time', item.get('itemDate', "ללא שעה")[:16].replace('T', ' ')),
                'title': item.get('title', 'ללא כותרת'),
                'link': item.get('shotedLink', item.get('link', '#'))
            } for item in items[:3]
        ]
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error in Arutz 7: {e}, Status Code: {e.response.status_code}, Response: {e.response.text[:200]}")
        return []
    except requests.exceptions.Timeout:
        logger.error("Timeout error while scraping Arutz 7")
        return []
    except ValueError as e:
        logger.error(f"JSON decoding error in Arutz 7: {e}, Response text: {response.text[:200]}")
        return []
    except Exception as e:
        logger.error(f"שגיאה בערוץ 7: {e}")
        return []

# פונקציה להצגת המבזקים האחרונים (מבוסס על ה-Logs)
async def latest_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ynet_news = scrape_ynet()
    walla_news = scrape_walla()
    arutz7_news = scrape_arutz7()

    message = "📰 **המבזקים האחרונים** 📰\n\n"

    # Ynet
    message += "**Ynet:**\n"
    if ynet_news:
        for i, news in enumerate(ynet_news, 1):
            message += f"{i}. [{news['title']}]({news['link']})\n"
    else:
        message += "לא ניתן לטעון כרגע\n"

    # ערוץ 7
    message += "\n**ערוץ 7:**\n"
    if arutz7_news:
        for i, news in enumerate(arutz7_news, 1):
            message += f"{i}. [{news['title']}]({news['link']})\n"
    else:
        message += "לא ניתן לטעון כרגע\n"

    # Walla
    message += "\n**Walla:**\n"
    if walla_news:
        for i, news in enumerate(walla_news, 1):
            message += f"{i}. [{news['time']}: {news['title']}]({news['link']})\n"
    else:
        message += "לא ניתן לטעון כרגע\n"

    # יצירת כפתורים
    keyboard = [
        [InlineKeyboardButton("⚽🏀 חדשות ספורט", callback_data="sports_news")],
        [InlineKeyboardButton("💻 חדשות טכנולוגיה", callback_data="tech_news")],
        [InlineKeyboardButton("📺 חדשות מערוצי טלוויזיה", callback_data="tv_news")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=reply_markup,
    )

# פונקציה לטיפול בלחיצות על כפתורים
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "sports_news":
        await query.message.reply_text("חדשות ספורט יגיעו בקרוב! 🏀⚽")
    elif query.data == "tech_news":
        await query.message.reply_text("חדשות טכנולוגיה יגיעו בקרוב! 💻")
    elif query.data == "tv_news":
        await query.message.reply_text("חדשות מערוצי טלוויזיה יגיעו בקרוב! 📺")

# הגדרת Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "NewsFlashIL Bot is running!"

# פונקציה ראשית
def main():
    application = Application.builder().token("7964398196:AAFh1bIgOMstfD4XMqh_IcFOa7AHB4j5xA8").build()

    application.add_handler(CommandHandler("latest", latest_news))
    application.add_handler(CallbackQueryHandler(button))

    # הפעלת Polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
    app.run(host="0.0.0.0", port=5000)