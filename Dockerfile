FROM python:3.9-slim

# התקנת כל התלויות הנדרשות ל-Chromium של Playwright
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
    libfontconfig1

# התקנת התלויות של Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# התקנת Playwright ו-Chromium
RUN pip install playwright
RUN playwright install

# העתקת הקוד לשרת
COPY . .

# פקודת הרצה
CMD ["python", "newsflashil.py"]