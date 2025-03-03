import pandas as pd
from datetime import datetime

log_data = []

def log_interaction(user_id, command, username=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data.append({
        "user_id": user_id,
        "command": command,
        "username": username if username else "N/A",  # שמירת שם המשתמש, או "N/A" אם אין
        "timestamp": timestamp
    })

def save_to_excel(filename="bot_usage.xlsx"):
    df = pd.DataFrame(log_data)
    df.to_excel(filename, index=False)
    return filename