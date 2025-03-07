from flask import Flask, request, Response
import requests
import os

app = Flask(__name__)
session = requests.Session()  # שמור עוגיות בין בקשות

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': target_url,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'  # דימוי דפדפן
        }
        response = session.get(target_url, headers=headers, timeout=10, allow_redirects=True)
        return Response(response.content, status=response.status_code, headers=dict(response.headers))
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
