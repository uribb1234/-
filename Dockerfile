FROM python:3.9-slim

# התקנת Tor
RUN apt-get update && apt-get install -y \
    tor \
    && rm -rf /var/lib/apt/lists/*

# העתקת קובץ torrc להגדרות Tor
COPY torrc /etc/tor/torrc

# העתקת requirements.txt והתקנת תלויות
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# העתקת קבצי הפרויקט
COPY . .

# הגדרת משתנה סביבה לפורט
ENV PORT=10000

# פתיחת פורטים עבור Flask ו-Tor
EXPOSE 10000 9050 9051

# הרצת Tor והסקריפט עם המתנה
CMD ["bash", "-c", "tor & sleep 10 && python newsflashil.py"]