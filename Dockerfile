FROM python:3.9-slim

# עדכון מערכת והתקנת תלויות בסיסיות
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# העתקת requirements.txt והתקנת תלויות
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# העתקת קבצי הפרויקט
COPY . .

# הגדרת משתנה סביבה לפורט
ENV PORT=10000

# פתיחת פורט עבור Flask
EXPOSE 10000

# הרצת הסקריפט
CMD ["python", "newsflashil.py"]