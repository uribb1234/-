from flask import Flask, request
import requests
import os

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400
    try:
        # הגדר headers מלאים לדימוי דפדפן
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com',
            'Connection': 'keep-alive'
        }
        # תמיכה בהפניות
        response = requests.get(target_url, headers=headers, timeout=10, allow_redirects=True)
        if response.status_code != 200:
            return f"Error from target: {response.status_code} - {response.text}", response.status_code
        return response.content, response.status_code, response.headers.items()
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
