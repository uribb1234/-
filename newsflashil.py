import os
import requests
from bs4 import BeautifulSoup
from telegram.ext import Updater, CommandHandler
from queue import Queue  # ייבוא Queue מהמודול הסטנדרטי של Python

# מקום להזין את הטוקן ישירות - תחליף את "YOUR_TOKEN_HERE" בטוקן שלך
# לדוגמה: "7964398196:ABCDEF..."
MY_TOKEN = "7964398196:AAGs-CWjj7gffnuZx94p7K2a_7K9TxAvvR0"

# הגדרת הטוקן - משתמש בטוקן מהקוד, או ממשתני הסביבה ב-Replit אם קיים
TOKEN = os.getenv("TELEGRAM_TOKEN") if os.getenv("TELEGRAM_TOKEN") else MY_TOKEN
if not TOKEN:
    print("שגיאה: הטוקן לא מוגדר! או שתזין אותו ב-MY_TOKEN בקוד, או תגדיר TELEGRAM_TOKEN במשתני הסביבה.")
    exit(1)

# קישורי אתרי החדשות
NEWS_SITES = {
    'ynet': 'https://www.ynet.co.il/news',
    'now14': 'https://www.now14.co.il/news-flash',
    'walla': 'https://news.walla.co.il/'
}


def start(update, context):
    print("קיבלתי פקודה: /start")
    update.message.reply_text(
        "ברוך הבא לבוט החדשות! השתמש בפקודה /latest כדי לקבל את המבזקים האחרונים."
    )


def scrape_ynet():
    try:
        response = requests.get(NEWS_SITES['ynet'])
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('div.slotTitle')[:5]
        return [{'title': item.text.strip(), 'link': item.find('a')['href']} for item in items]
    except Exception as e:
        print(f"שגיאה ב-Ynet: {str(e)}")
        return []


def scrape_now14():
    try:
        response = requests.get(NEWS_SITES['now14'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        print("מתחיל לגרד כתבות מ'מה שמעניין אתכם' ב-Now 14")

        news_container = soup.select_one('div.flex.flex-col.gap-y-[15px].w-full.lg\\:w-[288px]')
        if not news_container:
            print("לא נמצא הקונטיינר הראשי של 'מה שמעניין אתכם'")
            news_container = soup.find('div', class_='flex', string=lambda text: 'מה שמעניין אתכם' in (text or ''))
            if news_container:
                news_container = news_container.find_parent('div', class_='flex')
            if not news_container:
                print("גם הסלקטור החלופי לא מצא את הקונטיינר")
                return []

        print("נמצא קונטיינר: " + str(news_container.get('class')))

        sub_container = news_container.select_one('div.flex.flex-col.gap-y-[10px].lg\\:gap-y-[25px]')
        if not sub_container:
            print("לא נמצא תת-קונטיינר של הכתבות")
            return []

        news_items = sub_container.select('a[href^="/article/"]')
        if not news_items:
            print("לא נמצאו כתבות בתת-קונטיינר")
            return []

        results = []
        for item in news_items[:3]:
            try:
                title_elem = item.select_one('h1.text-[19px].leading-[22px].font-[600]')
                title = title_elem.text.strip() if title_elem else "ללא כותרת"
                link = item['href']
                if not link.startswith('http'):
                    link = f"https://www.now14.co.il{link}"
                results.append({'title': title, 'link': link})
                print(f"נמצאה כתבה: {title} - {link}")
            except Exception as e:
                print(f"שגיאה בעיבוד כתבה: {str(e)}")
                continue

        print(f"Now 14 scraping found {len(results)} items")
        return results

    except Exception as e:
        print(f"שגיאה כללית ב-Now 14: {str(e)}")
        return []


def scrape_walla():
    try:
        response = requests.get(NEWS_SITES['walla'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        newsflash_section = soup.select_one('div.top-section-newsflash.no-mobile')
        if not newsflash_section:
            print("לא נמצא אלמנט של המבזקים בוואלה")
            return []

        items = newsflash_section.select('a')
        results = []
        for item in items:
            title = item.get_text(strip=True)
            link = item['href']

            if title == "מבזקי חדשות" or title == "מבזקים":
                continue

            if len(title) > 5 and title[2] == ':':
                title = title[:5] + ": " + title[5:]

            if not link.startswith('http'):
                link = f"https://news.walla.co.il{link}"
            results.append({'title': title, 'link': link})

        print(f"Walla scraping found {len(results)} items")
        return results[:3]
    except Exception as e:
        print(f"שגיאה ב-Walla: {str(e)}")
        return []


def latest(update, context):
    print("קיבלתי פקודה: /latest")
    update.message.reply_text("מחפש את המבזקים האחרונים...")

    ynet_news = scrape_ynet()
    now14_news = scrape_now14()
    walla_news = scrape_walla()

    news = {'Ynet': ynet_news, 'Now 14': now14_news, 'Walla': walla_news}

    message = "\U0001F4F0 **המבזקים האחרונים** \U0001F4F0\n\n"
    for site, articles in news.items():
        message += f"**{site}:**\n"
        if articles:
            for idx, article in enumerate(articles[:3], 1):
                link = article['link']
                if link and not link.startswith('http'):
                    link = f"https://{link.lstrip('/')}"
                message += f"{idx}. [{article['title']}]({link})\n"
        else:
            message += "לא ניתן לטעון את החדשות כרגע\n"
        message += "\n"

    update.message.reply_text(text=message,
                              parse_mode='Markdown',
                              disable_web_page_preview=True)


def main():
    print("מנסה להתחבר לטלגרם עם הטוקן: " + TOKEN[:10] + "...")
    try:
        # יצירת תור לעדכונים והעברתו ל-Updater
        update_queue = Queue()
        updater = Updater(TOKEN, update_queue=update_queue)
        print("התחברתי לטלגרם בהצלחה!")
    except Exception as e:
        print(f"שגיאה בהתחברות לטלגרם: {str(e)}")
        return

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("latest", latest))

    print("מתחיל להריץ את הבוט...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()