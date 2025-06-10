# Zucchini Telegram Bot Core
# Developed modularly for easy expansion
# Hosting advice follows after the code section

import logging
import random
import time
import threading
import json
from collections import defaultdict
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, filters

# === Configurations ===
TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # Replace this with your actual bot token
DATA_FILE = 'zucchini_data.json'
LOTTERY_INTERVAL = 6 * 60 * 60  # 6 hours in seconds
GROUP_CHAT_ID = -1001234567890  # Replace with your actual group chat ID

# === Logging Setup ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === Data Persistence ===
try:
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    data = {
        'users': {},
        'duels': {},
        'lottery': {
            'bets': {},
            'history': [],
            'end_time': time.time() + LOTTERY_INTERVAL
        }
    }

# === Utility Functions ===
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in data['users']:
        data['users'][user_id] = {
            'length': 0,
            'last_daily': 0,
            'last_hourly': 0,
            'stats': {
                'daily_used': 0,
                'hourly_used': 0,
                'bet_total': 0,
                'won': 0,
                'lost': 0
            }
        }
    return data['users'][user_id]

def now():
    return time.time()

# === Leaderboard ===
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard_sorted = sorted(
        data['users'].items(), key=lambda x: x[1]['length'], reverse=True
    )[:10]
    msg = "🏆 Classifica Zucchine 🏆\n"
    for i, (uid, user) in enumerate(leaderboard_sorted, 1):
        msg += f"{i}. <a href=\"tg://user?id={uid}\">{uid}</a>: {user['length']}cm\n"
    await update.message.reply_text(msg, parse_mode='HTML')

# === Background Lottery Thread ===
def lottery_draw_loop():
    from telegram import Bot
    bot = Bot(token=TOKEN)
    while True:
        time.sleep(60)  # Check every minute
        if now() >= data['lottery']['end_time']:
            bets = data['lottery']['bets']
            if not bets:
                data['lottery']['end_time'] = now() + LOTTERY_INTERVAL
                save_data()
                continue
            winning_number = random.randint(1, 10)
            winners = [uid for uid, b in bets.items() if b['number'] == winning_number]
            total_pot = sum(b['amount'] for b in bets.values())
            winners_message = []
            losers_message = []
            if winners:
                share = total_pot // len(winners)
                for uid in winners:
                    get_user(uid)['length'] += share
                    winners_message.append(f"<a href=\"tg://user?id={uid}\">{uid}</a> (+{share}cm)")
            else:
                for uid, b in bets.items():
                    get_user(uid)['length'] += b['amount']  # refund
                    losers_message.append(f"<a href=\"tg://user?id={uid}\">{uid}</a> (rimborso {b['amount']}cm)")
            data['lottery']['history'].append(winning_number)
            data['lottery']['history'] = data['lottery']['history'][-5:]
            result_msg = f"\U0001F3B2 ESTRAZIONE SUPERENALOTTO \U0001F3B2\n"
            result_msg += f"Numero estratto: {winning_number}\n\n"
            result_msg += f"Totale scommesse: {total_pot}cm\n"
            if winners:
                result_msg += "Vincitori:\n" + "\n".join(winners_message)
            else:
                result_msg += "Nessun vincitore. Rimborso eseguito:\n" + "\n".join(losers_message)
            result_msg += f"\n\nProssima estrazione tra 6 ore."
            try:
                bot.send_message(chat_id=GROUP_CHAT_ID, text=result_msg, parse_mode='HTML')
            except Exception as e:
                logging.warning(f"Cannot send message to group: {e}")
            data['lottery']['bets'] = {}
            data['lottery']['end_time'] = now() + LOTTERY_INTERVAL
            save_data()

# Start lottery draw in background
threading.Thread(target=lottery_draw_loop, daemon=True).start()

# === Command Handlers ===
# ... [all previously defined command functions remain unchanged] ...

# === Bot Setup ===
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler('razione_giornaliera', razione_giornaliera, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('elemosina', elemosina, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('coinflip', coinflip, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('duello_pisello', duello_pisello, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('superenalotto', superenalotto, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('schedina', schedina, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('tessera_del_pane', tessera_del_pane, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('grazie_mosca', grazie_mosca, filters=filters.ChatType.GROUPS))
app.add_handler(CommandHandler('classifica', leaderboard, filters=filters.ChatType.GROUPS))
app.add_handler(CallbackQueryHandler(handle_duel_callback, pattern='^duel:'))
app.add_handler(CallbackQueryHandler(handle_donation, pattern='^donate:'))

# === Run the bot ===
if __name__ == '__main__':
    app.run_polling()

# === Hosting Advice ===
# 1. Heroku:
#    - Pro: Easy to deploy, well-documented
#    - Con: Free tier is limited, requires a workaround for 24/7 uptime
#    - Guide: Use a Procfile, requirements.txt, and set up Heroku dyno + scheduler for lottery
#
# 2. Railway (https://railway.app):
#    - Pro: Free hosting available, more modern and easier than Heroku
#    - Con: Free tier has limits too
#
# 3. Fly.io:
#    - Pro: Another free-tier PaaS that supports Python well
#    - Con: Slightly more technical setup
#
# 4. Local / Raspberry Pi / VPS:
#    - Pro: Full control, no limits
#    - Con: Requires maintenance

# I suggest starting with Railway if you want a modern and easy experience, or Heroku if you're already familiar.
# Remember to set up persistent storage or back up the JSON file externally.
# Let me know when you're ready for the remaining commands or deployment assistance.
