FROM python:3.9-slim
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1  # תלויות נדרשות ל-Chromium של Playwright
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install  # מתקין את Chromium של Playwright
COPY . .
CMD ["python", "newsflashil.py"]