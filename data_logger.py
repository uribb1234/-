from telegram.ext import Updater, CommandHandler
from data_logger import log_interaction, save_to_excel

# סיסמה פשוטה שרק אתה יודע
SECRET_PASSWORD = "urigili"

def start(update, context):
    user_id = update.message.from_user.id
    log_interaction(user_id, "/start")
    update.message.reply_text("ברוך הבא לבוט שלי!")

def download_stats(update, context):
    # בדיקת הסיסמה שהמשתמש שלח
    if not context.args or context.args[0] != SECRET_PASSWORD:
        update.message.reply_text("סיסמה שגויה! אין גישה.")
        return
    
    # יצירת ושליחת קובץ ה-Excel
    filename = save_to_excel()
    with open(filename, 'rb') as file:
        update.message.reply_document(document=file, filename="bot_usage.xlsx")
    update.message.reply_text("הנה הנתונים שלך!")

def main():
    updater = Updater("YOUR_BOT_TOKEN", use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("download", download_stats))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()