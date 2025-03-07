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
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"))
            )
            app.logger.info("Turnstile resolved or not present.")
        except Exception as e:
            app.logger.warning(f"Turnstile wait failed: {str(e)}, proceeding anyway...")

        # המתנה נוספת לדף הסופי
        sleep(2)
        content = driver.page_source
        app.logger.info("Content fetched, closing driver...")
        driver.quit()
        return Response(content, mimetype='text/html')
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
