from flask import Flask, request, Response
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
from time import sleep

app = Flask(__name__)

def get_driver():
    options = Options()
    options.add_argument("--headless")  # ריצה ללא GUI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = uc.Chrome(options=options)
    return driver

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400
    try:
        driver = get_driver()
        driver.get(target_url)
        sleep(5)  # חכה 5 שניות לפתרון אתגר Cloudflare
        content = driver.page_source
        driver.quit()
        return Response(content, mimetype='text/html')
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
