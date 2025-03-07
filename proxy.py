from flask import Flask, request, Response
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from time import sleep
import random

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        driver = uc.Chrome(options=options)
        
        # טען את הדף
        driver.get(target_url)

        # הוסף התנהגות אנושית
        try:
            # תנועת עכבר אקראית
            actions = ActionChains(driver)
            width, height = driver.execute_script("return [document.body.scrollWidth, document.body.scrollHeight];")
            x_move = random.randint(50, min(500, width - 50))
            y_move = random.randint(50, min(500, height - 50))
            actions.move_by_offset(x_move, y_move).perform()
            sleep(random.uniform(0.5, 1.5))  # המתנה קצרה כמו משתמש אמיתי

            # גלילה קלה
            driver.execute_script("window.scrollBy(0, 200);")
            sleep(random.uniform(0.5, 1.5))

            # המתנה קצרה נוספת לדימוי פעילות
            sleep(2)
        except Exception as e:
            pass  # המשך גם אם הפעולות נכשלות

        # קבל את התוכן הסופי
        content = driver.page_source
        driver.quit()

        # בדוק אם קיבלנו את ה-feed (XML)
        if "<rss" in content:
            return Response(content, mimetype='application/xml')
        else:
            return Response(content, mimetype='text/html')
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
