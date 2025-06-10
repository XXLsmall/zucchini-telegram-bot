# Zucchini Telegram Bot Core
# Improved version with security and reliability fixes

import logging
import random
import time
import threading
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Configurations ===
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID', '0'))
if GROUP_CHAT_ID == 0:
    raise ValueError("GROUP_CHAT_ID environment variable is required")

DATA_FILE = 'zucchini_data.json'
LOTTERY_INTERVAL = 6 * 60 * 60  # 6 hours in seconds

# === Logging Setup ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Thread Safety ===
data_lock = threading.Lock()

# === Data Persistence ===
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info("Data file not found, creating new data structure")
        return {
            'users': {},
            'duels': {},
            'lottery': {
                'bets': {},
                'history': [],
                'end_time': time.time() + LOTTERY_INTERVAL
            }
        }
    except json.JSONDecodeError as e:
        logger.error(f"Error loading data file: {e}")
        return {
            'users': {},
            'duels': {},
            'lottery': {
                'bets': {},
                'history': [],
                'end_time': time.time() + LOTTERY_INTERVAL
            }
        }

data = load_data()

# === Utility Functions ===
def save_data():
    try:
        with data_lock:
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def get_user(user_id):
    user_id = str(user_id)
    with data_lock:
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

# === Command Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "Benvenuto al bot delle zucchine! 🥒\n"
        "Usa /classifica per vedere la classifica."
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display leaderboard"""
    try:
        with data_lock:
            leaderboard_sorted = sorted(
                data['users'].items(), 
                key=lambda x: x[1]['length'], 
                reverse=True
            )[:10]
        
        if not leaderboard_sorted:
            await update.message.reply_text("Nessun utente nella classifica!")
            return
            
        msg = "🏆 Classifica Zucchine 🏆\n\n"
        for i, (uid, user) in enumerate(leaderboard_sorted, 1):
            try:
                # Try to get user info from Telegram
                chat_member = await context.bot.get_chat_member(update.effective_chat.id, int(uid))
                username = chat_member.user.first_name or f"User {uid}"
            except:
                username = f"User {uid}"
            
            msg += f"{i}. {username}: {user['length']}cm\n"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in leaderboard: {e}")
        await update.message.reply_text("Errore nel recuperare la classifica.")

# Placeholder functions for missing commands
async def razione_giornaliera(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Daily ration command - placeholder"""
    await update.message.reply_text("Comando razione_giornaliera non ancora implementato!")

async def elemosina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Donation command - placeholder"""
    await update.message.reply_text("Comando elemosina non ancora implementato!")

async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Coinflip command - placeholder"""
    await update.message.reply_text("Comando coinflip non ancora implementato!")

async def duello_pisello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Duel command - placeholder"""
    await update.message.reply_text("Comando duello_pisello non ancora implementato!")

async def superenalotto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lottery command - placeholder"""
    await update.message.reply_text("Comando superenalotto non ancora implementato!")

async def schedina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Betting slip command - placeholder"""
    await update.message.reply_text("Comando schedina non ancora implementato!")

async def tessera_del_pane(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bread card command - placeholder"""
    await update.message.reply_text("Comando tessera_del_pane non ancora implementato!")

async def grazie_mosca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Thank you command - placeholder"""
    await update.message.reply_text("Comando grazie_mosca non ancora implementato!")

async def handle_duel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle duel callback - placeholder"""
    query = update.callback_query
    await query.answer("Callback non ancora implementato!")

async def handle_donation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle donation callback - placeholder"""
    query = update.callback_query
    await query.answer("Callback non ancora implementato!")

# === Background Lottery Thread ===
def lottery_draw_loop():
    """Background lottery system"""
    bot = Bot(token=TOKEN)
    
    while True:
        try:
            time.sleep(60)  # Check every minute
            
            with data_lock:
                current_time = now()
                if current_time < data['lottery']['end_time']:
                    continue
                    
                bets = data['lottery']['bets'].copy()
                
            if not bets:
                with data_lock:
                    data['lottery']['end_time'] = current_time + LOTTERY_INTERVAL
                save_data()
                continue
                
            # Perform lottery draw
            winning_number = random.randint(1, 10)
            winners = [uid for uid, b in bets.items() if b['number'] == winning_number]
            total_pot = sum(b['amount'] for b in bets.values())
            
            winners_message = []
            losers_message = []
            
            with data_lock:
                if winners:
                    share = total_pot // len(winners)
                    for uid in winners:
                        get_user(uid)['length'] += share
                        winners_message.append(f"User {uid} (+{share}cm)")
                else:
                    # Refund bets if no winners
                    for uid, b in bets.items():
                        get_user(uid)['length'] += b['amount']
                        losers_message.append(f"User {uid} (rimborso {b['amount']}cm)")
                
                # Update lottery data
                data['lottery']['history'].append(winning_number)
                data['lottery']['history'] = data['lottery']['history'][-5:]
                data['lottery']['bets'] = {}
                data['lottery']['end_time'] = current_time + LOTTERY_INTERVAL
            
            save_data()
            
            # Send results
            result_msg = f"🎲 ESTRAZIONE SUPERENALOTTO 🎲\n"
            result_msg += f"Numero estratto: {winning_number}\n\n"
            result_msg += f"Totale scommesse: {total_pot}cm\n"
            
            if winners:
                result_msg += "Vincitori:\n" + "\n".join(winners_message)
            else:
                result_msg += "Nessun vincitore. Rimborso eseguito:\n" + "\n".join(losers_message)
            
            result_msg += f"\n\nProssima estrazione tra 6 ore."
            
            try:
                bot.send_message(chat_id=GROUP_CHAT_ID, text=result_msg)
            except Exception as e:
                logger.error(f"Cannot send message to group: {e}")
                
        except Exception as e:
            logger.error(f"Error in lottery loop: {e}")
            time.sleep(300)  # Wait 5 minutes on error

# === Error Handler ===
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# === Bot Setup ===
def main():
    """Main function to run the bot"""
    # Start lottery thread
    lottery_thread = threading.Thread(target=lottery_draw_loop, daemon=True)
    lottery_thread.start()
    
    # Build application
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler('start', start))
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
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    logger.info("Bot started successfully")
    app.run_polling()

if __name__ == '__main__':
    main()