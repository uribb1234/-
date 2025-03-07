from flask import Flask, request, Response
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from time import sleep

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400
    try:
        app.logger.info("Starting Chrome driver...")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        driver = uc.Chrome(options=options)
        app.logger.info(f"Fetching URL: {target_url}")
        driver.get(target_url)

        # המתנה לאתגר Cloudflare Turnstile
        app.logger.info("Waiting for Cloudflare Turnstile to resolve...")
        try:
            # חכה עד שה-iframe של Turnstile נעלם או עד שהתוכן הסופי מופיע
            WebDriverWait(driver, 20).until(
                lambda driver: "challenges.cloudflare.com" not in driver.page_source or \
                               EC.presence_of_element_located((By.TAG_NAME, "rss"))
            )
            app.logger.info("Turnstile resolved or feed loaded.")
        except Exception as e:
            app.logger.warning(f"Turnstile wait failed: {str(e)}, proceeding with current page...")

        # המתנה נוספת לדף הסופי
        sleep(2)
        content = driver.page_source
        app.logger.info("Content fetched, closing driver...")
        driver.quit()

        # בדוק אם קיבלנו את ה-feed (XML)
        if "<rss" in content:
            app.logger.info("RSS feed detected.")
            return Response(content, mimetype='application/xml')
        else:
            app.logger.warning("RSS feed not found, returning HTML.")
            return Response(content, mimetype='text/html')
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
