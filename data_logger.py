import pandas as pd
from datetime import datetime

log_data = []

def log_interaction(user_id, command):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data.append({"user_id": user_id, "command": command, "timestamp": timestamp})

def save_to_excel(filename="bot_usage.xlsx"):
    df = pd.DataFrame(log_data)
    df.to_excel(filename, index=False)
    return filename