from flask import Flask, request, Response
import os
import undetected_chromedriver.v2 as uc
from time import sleep

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400
    try:
        # הגדרת אפשרויות לדפדפן
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--start-maximized')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        # אתחול הדפדפן
        driver = uc.Chrome(options=options)
        
        # גישה ל-URL
        driver.get(target_url)
        driver.implicitly_wait(10)  # המתנה של 10 שניות לטעינה

        # קבל את התוכן
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
