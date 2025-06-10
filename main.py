# Zucchini Telegram Bot Core
# Fixed version with working commands and no group restrictions

import logging
import random
import time
import threading
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Configurations ===
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

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
                'length': 10,  # Starting length
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

def get_username(user):
    """Get a display name for a user"""
    if user.username:
        return f"@{user.username}"
    elif user.first_name:
        return user.first_name
    else:
        return f"User {user.id}"

# === Command Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = get_user(update.effective_user.id)
    save_data()
    
    await update.message.reply_text(
        f"Benvenuto al bot delle zucchine! 🥒\n"
        f"La tua zucchina attuale: {user['length']}cm\n\n"
        f"Comandi disponibili:\n"
        f"/classifica - Visualizza la classifica\n"
        f"/razione_giornaliera - Ottieni la tua razione giornaliera\n"
        f"/elemosina - Chiedi l'elemosina\n"
        f"/coinflip [puntata] - Scommetti su testa o croce\n"
        f"/duello_pisello [@utente] - Sfida un utente a duello\n"
        f"/superenalotto [numero] [puntata] - Partecipa alla lotteria\n"
        f"/schedina - Vedi la tua schedina del superenalotto\n"
        f"/tessera_del_pane - Ritira il pane gratuito\n"
        f"/grazie_mosca - Ringrazia per un favore ricevuto"
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
        for i, (uid, user_data) in enumerate(leaderboard_sorted, 1):
            try:
                # Try to get user info from Telegram
                user_obj = await context.bot.get_chat_member(update.effective_chat.id, int(uid))
                username = get_username(user_obj.user)
            except:
                username = f"User {uid}"
            
            msg += f"{i}. {username}: {user_data['length']}cm\n"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in leaderboard: {e}")
        await update.message.reply_text("Errore nel recuperare la classifica.")

async def razione_giornaliera(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Daily ration command"""
    user = get_user(update.effective_user.id)
    current_time = now()
    
    # Check if user already used daily ration today (24 hours)
    if current_time - user['last_daily'] < 24 * 60 * 60:
        remaining = 24 * 60 * 60 - (current_time - user['last_daily'])
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await update.message.reply_text(
            f"Hai già ritirato la tua razione oggi! 🍞\n"
            f"Prossima razione disponibile tra: {hours}h {minutes}m"
        )
        return
    
    # Give daily ration
    bonus = random.randint(3, 8)
    user['length'] += bonus
    user['last_daily'] = current_time
    user['stats']['daily_used'] += 1
    save_data()
    
    await update.message.reply_text(
        f"Hai ritirato la tua razione giornaliera! 🍞\n"
        f"Guadagno: +{bonus}cm\n"
        f"Zucchina attuale: {user['length']}cm"
    )

async def elemosina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Donation request command"""
    user = get_user(update.effective_user.id)
    current_time = now()
    
    # Check if user already used elemosina in the last hour
    if current_time - user['last_hourly'] < 60 * 60:
        remaining = 60 * 60 - (current_time - user['last_hourly'])
        minutes = int(remaining // 60)
        await update.message.reply_text(
            f"Hai già chiesto l'elemosina di recente! 🙏\n"
            f"Riprova tra: {minutes} minuti"
        )
        return
    
    # Random chance of getting donation
    if random.random() < 0.3:  # 30% chance
        bonus = random.randint(1, 3)
        user['length'] += bonus
        user['last_hourly'] = current_time
        user['stats']['hourly_used'] += 1
        save_data()
        
        await update.message.reply_text(
            f"Un gentile signore ti ha dato l'elemosina! 🪙\n"
            f"Guadagno: +{bonus}cm\n"
            f"Zucchina attuale: {user['length']}cm"
        )
    else:
        user['last_hourly'] = current_time
        save_data()
        await update.message.reply_text(
            "Nessuno ti ha dato l'elemosina questa volta... 😔\n"
            "Riprova tra un'ora!"
        )

async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Coinflip betting command"""
    user = get_user(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text(
            "Uso: /coinflip [puntata]\n"
            f"La tua zucchina attuale: {user['length']}cm"
        )
        return
    
    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text("La puntata deve essere un numero!")
        return
    
    if bet <= 0:
        await update.message.reply_text("La puntata deve essere maggiore di 0!")
        return
    
    if bet > user['length']:
        await update.message.reply_text(
            f"Non hai abbastanza cm! Hai: {user['length']}cm, vuoi scommettere: {bet}cm"
        )
        return
    
    # Coinflip logic
    result = random.choice(['testa', 'croce'])
    win = random.random() < 0.5  # 50% chance to win
    
    if win:
        user['length'] += bet
        user['stats']['won'] += 1
        await update.message.reply_text(
            f"🪙 TESTA O CROCE 🪙\n"
            f"Risultato: {result.upper()}\n"
            f"HAI VINTO! 🎉\n"
            f"Guadagno: +{bet}cm\n"
            f"Zucchina attuale: {user['length']}cm"
        )
    else:
        user['length'] -= bet
        user['stats']['lost'] += 1
        await update.message.reply_text(
            f"🪙 TESTA O CROCE 🪙\n"
            f"Risultato: {result.upper()}\n"
            f"Hai perso... 😔\n"
            f"Perdita: -{bet}cm\n"
            f"Zucchina attuale: {user['length']}cm"
        )
    
    user['stats']['bet_total'] += bet
    save_data()

async def duello_pisello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Duel command"""
    if not context.args:
        await update.message.reply_text(
            "Uso: /duello_pisello [@username o rispondi a un messaggio]\n"
            "Sfida un utente a duello!"
        )
        return
    
    challenger = get_user(update.effective_user.id)
    challenger_name = get_username(update.effective_user)
    
    # Create duel invitation
    keyboard = [[
        InlineKeyboardButton("Accetta Duello ⚔️", callback_data=f"duel:accept:{update.effective_user.id}"),
        InlineKeyboardButton("Rifiuta Duello ❌", callback_data=f"duel:decline:{update.effective_user.id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚔️ DUELLO LANCIATO! ⚔️\n"
        f"{challenger_name} ha sfidato {context.args[0]} a duello!\n"
        f"Zucchina sfidante: {challenger['length']}cm\n\n"
        f"Il duello è una battaglia all'ultimo cm!\n"
        f"Il vincitore prende il 20% della zucchina del perdente!",
        reply_markup=reply_markup
    )

async def superenalotto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lottery betting command"""
    user = get_user(update.effective_user.id)
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "Uso: /superenalotto [numero 1-10] [puntata]\n"
            f"La tua zucchina attuale: {user['length']}cm\n"
            f"Prossima estrazione tra: {int((data['lottery']['end_time'] - now()) / 3600)}h"
        )
        return
    
    try:
        number = int(context.args[0])
        bet = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Numero e puntata devono essere numeri!")
        return
    
    if not (1 <= number <= 10):
        await update.message.reply_text("Il numero deve essere tra 1 e 10!")
        return
    
    if bet <= 0:
        await update.message.reply_text("La puntata deve essere maggiore di 0!")
        return
    
    if bet > user['length']:
        await update.message.reply_text(
            f"Non hai abbastanza cm! Hai: {user['length']}cm, vuoi scommettere: {bet}cm"
        )
        return
    
    user_id = str(update.effective_user.id)
    
    # Add/update bet
    with data_lock:
        if user_id in data['lottery']['bets']:
            # Refund previous bet
            user['length'] += data['lottery']['bets'][user_id]['amount']
        
        data['lottery']['bets'][user_id] = {
            'number': number,
            'amount': bet
        }
        user['length'] -= bet
    
    save_data()
    
    remaining_time = int((data['lottery']['end_time'] - now()) / 3600)
    total_bets = len(data['lottery']['bets'])
    
    await update.message.reply_text(
        f"🎲 SCOMMESSA REGISTRATA! 🎲\n"
        f"Numero scelto: {number}\n"
        f"Puntata: {bet}cm\n"
        f"Zucchina rimanente: {user['length']}cm\n\n"
        f"Partecipanti totali: {total_bets}\n"
        f"Prossima estrazione tra: {remaining_time}h"
    )

async def schedina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's betting slip"""
    user_id = str(update.effective_user.id)
    user = get_user(update.effective_user.id)
    
    msg = f"📋 LA TUA SCHEDINA 📋\n"
    msg += f"Zucchina attuale: {user['length']}cm\n\n"
    
    with data_lock:
        if user_id in data['lottery']['bets']:
            bet = data['lottery']['bets'][user_id]
            remaining_time = int((data['lottery']['end_time'] - now()) / 3600)
            msg += f"🎲 SUPERENALOTTO:\n"
            msg += f"Numero scommesso: {bet['number']}\n"
            msg += f"Puntata: {bet['amount']}cm\n"
            msg += f"Estrazione tra: {remaining_time}h\n\n"
        else:
            msg += "Nessuna scommessa attiva al superenalotto\n\n"
    
    msg += f"📊 STATISTICHE:\n"
    msg += f"Razioni giornaliere usate: {user['stats']['daily_used']}\n"
    msg += f"Elemosine ricevute: {user['stats']['hourly_used']}\n"
    msg += f"Scommesse vinte: {user['stats']['won']}\n"
    msg += f"Scommesse perse: {user['stats']['lost']}\n"
    msg += f"Totale scommesso: {user['stats']['bet_total']}cm"
    
    await update.message.reply_text(msg)

async def tessera_del_pane(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Free bread command"""
    user = get_user(update.effective_user.id)
    current_time = now()
    
    # Check if user already got bread today
    last_bread = user.get('last_bread', 0)
    if current_time - last_bread < 24 * 60 * 60:
        remaining = 24 * 60 * 60 - (current_time - last_bread)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await update.message.reply_text(
            f"Hai già ritirato il pane oggi! 🍞\n"
            f"Prossimo ritiro tra: {hours}h {minutes}m"
        )
        return
    
    # Give free bread (small amount)
    bonus = random.randint(1, 3)
    user['length'] += bonus
    user['last_bread'] = current_time
    save_data()
    
    await update.message.reply_text(
        f"Hai ritirato il pane gratuito! 🍞\n"
        f"Guadagno: +{bonus}cm\n"
        f"Zucchina attuale: {user['length']}cm\n"
        f"Torna domani per altro pane gratuito!"
    )

async def grazie_mosca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Thank you command"""
    user = get_user(update.effective_user.id)
    
    # Small random bonus for being polite
    if random.random() < 0.1:  # 10% chance
        bonus = 1
        user['length'] += bonus
        save_data()
        await update.message.reply_text(
            f"Grazie della cortesia! 🙏\n"
            f"Per la tua gentilezza: +{bonus}cm\n"
            f"Zucchina attuale: {user['length']}cm"
        )
    else:
        await update.message.reply_text(
            "Prego! La cortesia è sempre apprezzata! 🙏"
        )

async def handle_duel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle duel callback"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, challenger_id = query.data.split(':')[1:3]
        challenger_id = int(challenger_id)
        
        if query.from_user.id == challenger_id:
            await query.edit_message_text("Non puoi accettare il tuo stesso duello!")
            return
        
        challenger = get_user(challenger_id)
        defender = get_user(query.from_user.id)
        
        if action == "accept":
            # Duel logic
            challenger_roll = random.randint(1, 20)
            defender_roll = random.randint(1, 20)
            
            if challenger_roll > defender_roll:
                # Challenger wins
                prize = int(defender['length'] * 0.2)
                challenger['length'] += prize
                defender['length'] -= prize
                winner_name = "Sfidante"
                result_msg = f"⚔️ DUELLO CONCLUSO! ⚔️\n\n"
                result_msg += f"Sfidante: {challenger_roll} 🎲\n"
                result_msg += f"Difensore: {defender_roll} 🎲\n\n"
                result_msg += f"🏆 VINCE LO SFIDANTE!\n"
                result_msg += f"Premio: {prize}cm trasferiti!"
            elif defender_roll > challenger_roll:
                # Defender wins
                prize = int(challenger['length'] * 0.2)
                defender['length'] += prize
                challenger['length'] -= prize
                result_msg = f"⚔️ DUELLO CONCLUSO! ⚔️\n\n"
                result_msg += f"Sfidante: {challenger_roll} 🎲\n"
                result_msg += f"Difensore: {defender_roll} 🎲\n\n"
                result_msg += f"🏆 VINCE IL DIFENSORE!\n"
                result_msg += f"Premio: {prize}cm trasferiti!"
            else:
                # Tie
                result_msg = f"⚔️ DUELLO CONCLUSO! ⚔️\n\n"
                result_msg += f"Sfidante: {challenger_roll} 🎲\n"
                result_msg += f"Difensore: {defender_roll} 🎲\n\n"
                result_msg += f"🤝 PAREGGIO!\n"
                result_msg += f"Nessun trasferimento di cm!"
            
            save_data()
            await query.edit_message_text(result_msg)
            
        elif action == "decline":
            await query.edit_message_text(
                f"🚫 DUELLO RIFIUTATO!\n"
                f"Il difensore ha rifiutato la sfida."
            )
            
    except Exception as e:
        logger.error(f"Error in duel callback: {e}")
        await query.edit_message_text("Errore nel duello!")

async def handle_donation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle donation callback - placeholder"""
    query = update.callback_query
    await query.answer("Funzione donazione non ancora implementata!")

# === Background Lottery Thread ===
def lottery_draw_loop():
    """Background lottery system"""
    
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
            
            with data_lock:
                if winners:
                    share = total_pot // len(winners)
                    for uid in winners:
                        get_user(uid)['length'] += share
                        logger.info(f"Lottery winner: User {uid} won {share}cm")
                else:
                    # Refund bets if no winners
                    for uid, b in bets.items():
                        get_user(uid)['length'] += b['amount']
                        logger.info(f"Lottery refund: User {uid} refunded {b['amount']}cm")
                
                # Update lottery data
                data['lottery']['history'].append(winning_number)
                data['lottery']['history'] = data['lottery']['history'][-5:]
                data['lottery']['bets'] = {}
                data['lottery']['end_time'] = current_time + LOTTERY_INTERVAL
            
            save_data()
            logger.info(f"Lottery draw completed. Winning number: {winning_number}, Total pot: {total_pot}cm")
                
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
    
    # Add handlers - REMOVED GROUP FILTERS
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('razione_giornaliera', razione_giornaliera))
    app.add_handler(CommandHandler('elemosina', elemosina))
    app.add_handler(CommandHandler('coinflip', coinflip))
    app.add_handler(CommandHandler('duello_pisello', duello_pisello))
    app.add_handler(CommandHandler('superenalotto', superenalotto))
    app.add_handler(CommandHandler('schedina', schedina))
    app.add_handler(CommandHandler('tessera_del_pane', tessera_del_pane))
    app.add_handler(CommandHandler('grazie_mosca', grazie_mosca))
    app.add_handler(CommandHandler('classifica', leaderboard))
    app.add_handler(CallbackQueryHandler(handle_duel_callback, pattern='^duel:'))
    app.add_handler(CallbackQueryHandler(handle_donation, pattern='^donate:'))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    logger.info("Bot started successfully")
    app.run_polling()

if __name__ == '__main__':
    main()