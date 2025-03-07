FROM python:3.9-slim

# התקנת כל התלויות הנדרשות לדפדפנים ול-xvfb
RUN apt-get update && apt-get install -y \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxcb1 \
    libxkbcommon0 \
    libasound2 \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    xvfb

# התקנת Playwright ותלויות נוספות
RUN pip install playwright
RUN playwright install-deps
RUN playwright install

# התקנת התלויות של Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# העתקת הקוד לשרת
COPY . .

# הגדרת משתנה סביבה לפורט
ENV PORT=8080

# הרצת הבוט עם xvfb ושרת Flask כתהליך ראשי
CMD ["xvfb-run", "--auto-servernum", "python", "newsflashil.py"]
