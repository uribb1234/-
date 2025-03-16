import pandas as pd
from datetime import datetime
import os
import atexit

LOG_FILE = "bot_usage_log.csv"
log_data = []

# טען נתונים קיימים מהקובץ בהתחלה (אם קיים)
if os.path.exists(LOG_FILE):
    df = pd.read_csv(LOG_FILE)
    log_data = df.to_dict('records')  # המרת ה-DataFrame לרשימה של מילונים

def log_interaction(user_id, command, username=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data.append({
        "user_id": user_id,
        "command": command,
        "username": username if username else "N/A",
        "timestamp": timestamp
    })

def save_log_to_file():
    """שמור את log_data לקובץ CSV"""
    df = pd.DataFrame(log_data)
    df.to_csv(LOG_FILE, index=False)

def save_to_excel(filename="bot_usage.xlsx"):
    df = pd.DataFrame(log_data)
    df.to_excel(filename, index=False)
    save_log_to_file()  # גיבוי ל-CSV בזמן ההורדה
    return filename

# שמור את הלוג לקובץ כשהתוכנית נסגרת (למשל, ב-Deploy חדש)
atexit.register(save_log_to_file)
