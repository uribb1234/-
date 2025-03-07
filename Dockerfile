FROM python:3.9-slim

# עדכון חבילות והתקנת תלויות Playwright ו-Tor
RUN apt-get update && apt-get install -y \
    libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libx11-6 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libxcb1 libxkbcommon0 \
    libasound2 libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 xvfb \
    tor \
    && rm -rf /var/lib/apt/lists/*

# התקנת Playwright ותלויותיו
RUN pip install playwright
RUN playwright install-deps
RUN playwright install

# העתקת requirements.txt והתקנת תלויות Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# העתקת כל קבצי הפרויקט
COPY . .

# הגדרת משתנה סביבה לפורט
ENV PORT=10000

# פתיחת פורטים עבור Flask ו-Tor
EXPOSE 10000 9050 9051

# הרצת Tor ברקע והסקריפט הראשי
CMD ["bash", "-c", "tor & python newsflashil.py"]