FROM python:3.9-slim

# התקנת תלויות לדפדפנים ול-xvfb
RUN apt-get update && apt-get install -y \
    libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libx11-6 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libxcb1 libxkbcommon0 \
    libasound2 libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 xvfb

# התקנת Playwright
RUN pip install playwright
RUN playwright install-deps
RUN playwright install

# התקנת תלויות Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# העתקת הקוד
COPY . .

# הגדרת פורט ברירת מחדל ל-10000 (תואם ל-Render)
ENV PORT=10000

# הרצת הסקריפט ישירות (בלי xvfb-run ב-CMD, נטפל בזה בקוד)
CMD ["python", "newsflashil.py"]
