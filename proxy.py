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
        # הוסף User-Agent כדי לדמות דפדפן
        headers = dict(request.headers)
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        response = requests.get(target_url, headers=headers, timeout=10)
        return response.content, response.status_code, response.headers.items()
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
