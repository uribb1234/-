from flask import Flask, request, Response
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from time import sleep
import random
import requests
import json
from datetime import datetime, timedelta

app = Flask(__name__)

# מטמון עבור תוכן
CACHE_FILE = "cache.json"
REQUEST_COUNT_FILE = "request_count.json"
DAILY_LIMIT = 100

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def load_request_count():
    try:
        with open(REQUEST_COUNT_FILE, "r") as f:
            data = json.load(f)
            date = datetime.strptime(data["date"], "%Y-%m-%d")
            if date.date() != datetime.now().date():
                return {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}
            return data
    except:
        return {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}

def save_request_count(count_data):
    with open(REQUEST_COUNT_FILE, "w") as f:
        json.dump(count_data, f)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400

    # טען מטמון וספירת בקשות
    cache = load_cache()
    request_count = load_request_count()

    # בדוק אם עברנו את המגבלה
    if request_count["count"] >= DAILY_LIMIT:
        if target_url in cache:
            content = cache[target_url]["content"]
            mime_type = cache[target_url]["mime_type"]
            return Response(content, mimetype=mime_type)
        return "Error: Daily request limit reached for NopeCHA", 429

    try:
        # הגדרת אפשרויות לדפדפן
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        # אתחול הדפדפן
        driver = uc.Chrome(options=options)
        driver.get(target_url)

        # המתנה ל-Turnstile
        try:
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"))
            )

            # שליפת ה-Sitekey
            sitekey = driver.find_element(By.CSS_SELECTOR, 'div[data-sitekey]').get_attribute('data-sitekey')
            driver.switch_to.default_content()

            # עדכן ספירת בקשות
            request_count["count"] += 1
            save_request_count(request_count)

            # שימוש ב-NopeCHA לפתרון CAPTCHA
            api_key = "YOUR_NOPECHA_API_KEY"  # החלף ב-API Key שלך מ-NopeCHA
            payload = {
                "key": api_key,
                "method": "turnstile",
                "sitekey": sitekey,
                "url": target_url
            }
            response = requests.post("https://api.nopecha.com", json=payload)
            result = response.json()
            if "error" in result:
                if target_url in cache:
                    content = cache[target_url]["content"]
                    mime_type = cache[target_url]["mime_type"]
                    return Response(content, mimetype=mime_type)
                return f"Error: NopeCHA failed - {result['error']}", 500

            token = result.get("token")
            if not token:
                if target_url in cache:
                    content = cache[target_url]["content"]
                    mime_type = cache[target_url]["mime_type"]
                    return Response(content, mimetype=mime_type)
                return "Error: No token received from NopeCHA", 500

            # הזרקת הטוקן
            driver.execute_script(f"document.getElementById('cf-turnstile-response').value = '{token}';")
            driver.switch_to.default_content()

            # המתנה לפתרון
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"))
            )
        except:
            pass  # המשך אם אין Turnstile

        # הוסף התנהגות אנושית
        actions = webdriver.ActionChains(driver)
        actions.move_by_offset(random.randint(100, 500), random.randint(100, 500)).perform()
        sleep(random.uniform(0.5, 1.5))
        driver.execute_script("window.scrollBy(0, 200);")
        sleep(random.uniform(0.5, 1.5))
        actions.click().perform()
        sleep(2)

        # קבל את התוכן
        content = driver.page_source
        driver.quit()

        # בדוק את התוכן
        mime_type = 'text/html'
        if "<rss" in content or "GetNews" in content:
            if "<rss" in content:
                mime_type = 'application/xml'
            else:
                mime_type = 'text/html'
        
        # שמור במטמון
        cache[target_url] = {"content": content, "mime_type": mime_type}
        save_cache(cache)

        return Response(content, mimetype=mime_type)
    except Exception as e:
        if target_url in cache:
            content = cache[target_url]["content"]
            mime_type = cache[target_url]["mime_type"]
            return Response(content, mimetype=mime_type)
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
