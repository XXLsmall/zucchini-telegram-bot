# Zucchini Telegram Bot Core
# Fixed version with working commands and no group restrictions

import logging
import random
import time
import threading
import json
import os
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Configurations ===
TOKEN = os.getenv('BOT_TOKEN')
FIXED_GROUP_CHAT_ID = -4951349977
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

DATA_FILE = 'zucchini_data.json'
LOTTERY_INTERVAL = 1 * 45  # 6 hours in seconds

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
    if user_id not in data['users']:
        data['users'][user_id] = {
            "length": 20,
            "last_daily": 0,
            "last_beg": 0,
            "stats": {
                "daily_collected": 0,
                "begs": 0,
                "length_won": 0,
                "length_lost": 0,
            },
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
    chat_id = update.effective_chat.id
    msg_text = update.message.text

    logger.info(f"Group ID: {chat_id}")
    logger.info(f"Message length: {len(msg_text)}")
    logger.debug(f"Message content:\n{msg_text}")
    
    await update.message.reply_text(
        f"Benvenuto al bot della ludopatia! 🎰\n"
        f"Il tuo cazzone è lungo: {user['length']}cm\n\n"
        f"Comandi disponibili:\n"
        f"/classifica - Visualizza la classifica\n"
        f"/razione_giornaliera - Ottieni la tua razione giornaliera\n"
        f"/elemosina - Chiedi l'elemosina\n"
        f"/coinflip [puntata] - Scommetti su falce o martello\n"
        f"/duello_pisello [puntata] - Come il bot vecchio dioporco\n"
        f"/superenalotto - Vedi i dati sulla lotteria\n"
        f"/schedina [numero 1-10] [puntata] - Compra una schedina, puoi comprarne quante ne vuoi dello stesso numero\n"
        f"/tessera_del_pane - Vedi quanto sei ludopatico\n"
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
            
        msg = "🎰 Classifica Ludopatici 🎰\n\n"
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
            f"Hai già ritirato la tua razione oggi! 🤬\n"
            f"Prossima razione disponibile tra: {hours} ore {minutes} minuti"
        )
        return
    
    # Give daily ration
    bonus = random.randint(5, 15)
    user['length'] += bonus
    user['last_daily'] = current_time
    user['stats']['daily_used'] += 1
    save_data()
    
    await update.message.reply_text(
        f"Hai ritirato la tua razione giornaliera! 🎲\n"
        f"Hai ottenuto: +{bonus}cm\n"
        f"Nerchia attuale: {user['length']}cm"
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
            f"Hai già chiesto l'elemosina ritardato! 🤡\n"
            f"Riprova tra: {minutes} minuti se hai le palle"
        )
        return
    
    # Random chance of getting donation
    bonus = random.randint(3, 9)
    user['length'] += bonus
    user['last_hourly'] = current_time
    user['stats']['hourly_used'] += 1
    save_data()

    await update.message.reply_text(
        f"Il duce ti ha dato l'elemosina! 🙋🏻‍♂\n"
        f"Ottieni +{bonus}cm\n"
        f"Minchia attuale: {user['length']}cm"
    )


async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    user_id = str(update.effective_user.id)

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Brutto ritardato, scrivi: /coinflip [puntata]")
        return

    bet = int(context.args[0])
    if bet <= 0 or bet > user['length']:
        await update.message.reply_text(f"Puntata non valida. Hai solo {user['length']}cm sfigato.")
        return

    data['duels'][user_id] = {'bet': bet, 'type': 'coinflip'}
    save_data()

    keyboard = [
        [InlineKeyboardButton("🚬 Cannetta", callback_data=f"coinflip:{user_id}:cannetta")],
        [InlineKeyboardButton("💣 Cannone", callback_data=f"coinflip:{user_id}:cannone")]
    ]
    await update.message.reply_text(
        f"Stai per giocare al coinflip {bet}cm!\nScegli:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def duello_pisello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Brutto ritardato, scrivi: /duello_pisello [puntata]")
        return

    bet = int(context.args[0])
    user_id = str(update.effective_user.id)
    user = get_user(user_id)

    if bet <= 0 or bet > user['length']:
        await update.message.reply_text(f"Puntata invalida, come te. Hai {user['length']}cm.")
        return

    data['duels'][user_id] = {'bet': bet}
    save_data()

    keyboard = [[InlineKeyboardButton("Duello per l'onore ⚔️", callback_data=f"duel:accept:{user_id}")]]
    await update.message.reply_text(
        f"⚔️ {get_username(update.effective_user)} ha lanciato un duello da {bet}cm!\n"
        f"Vincere, e vinceremo!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def superenalotto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    msg = "🎰 SCOMMESSE ATTUALI 🎰\n\n"

    with data_lock:
        active_bets = {}
        for uid, b in data['lottery']['bets'].items():
            num = b['number']
            active_bets.setdefault(num, []).append((uid, b['amount']))

        for num, entries in active_bets.items():
            total = sum(a for _, a in entries)
            msg += f"{num}: {total}cm da {len(entries)} fascisti\n"

        if user_id in data['lottery']['bets']:
            own = data['lottery']['bets'][user_id]
            msg += f"\nTe hai puntato {own['amount']}cm sul numero {own['number']}, io consiglierei di puntare di più"

        remaining_sec = int(data['lottery']['end_time'] - now())
        hours = remaining_sec // 3600
        minutes = (remaining_sec % 3600) // 60
        seconds = remaining_sec % 60
        msg += f"\n⏰ Prossima estrazione tra: {hours}h {minutes}m {seconds}s"

    await update.message.reply_text(msg)

async def schedina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = get_user(user_id)

    if len(context.args) != 2:
        await update.message.reply_text("Brutto ritardato, scrivi: /schedina [numero 1-10] [puntata]")
        return

    try:
        number = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Non sai contare?")
        return

    if not (1 <= number <= 10) or amount <= 0 or amount > user['length']:
        await update.message.reply_text("O non sai contare o lo hai troppo piccolo, scommessa rifiutata coglione!")
        return

    user['length'] -= amount

    with data_lock:
        # Set end time if expired
        if now() >= data['lottery'].get('end_time', 0):
            data['lottery']['end_time'] = now() + LOTTERY_INTERVAL

        current_bet = data['lottery']['bets'].get(user_id)
        if current_bet:
            if current_bet['number'] != number:
                await update.message.reply_text("Hai già scommesso su un altro numero mongolo!")
                return
            current_bet['amount'] += amount
        else:
            data['lottery']['bets'][user_id] = {'number': number, 'amount': amount}


    save_data()
    await update.message.reply_text(f"✅ Hai fatto bene a puntare di più! Totale: {data['lottery']['bets'][user_id]['amount']}cm sul numero {number}")


async def tessera_del_pane(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    daily = user['stats'].get('daily_used', 0)
    hourly = user['stats'].get('hourly_used', 0)

    await update.message.reply_text(
        f"💰 Tessera del Pane 💰\n"
        f"Razioni giornaliere ottenute: {daily} volte\n"
        f"Elemosine ricevute: {hourly} volte\n"
        f"Dovresti essere più ludopatico"
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

async def handle_coinflip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        _, user_id, choice = query.data.split(":")
        actor_id = str(query.from_user.id)

        if actor_id != user_id:
            await query.answer("Non toccare porcodio, solo chi lo ha creato può giocare!", show_alert=True)
            return

        bet_data = data['duels'].get(user_id)
        if not bet_data or bet_data.get('type') != 'coinflip':
            await query.edit_message_text("Coinflip non valido o già completato.")
            return

        user = get_user(user_id)
        bet = bet_data['bet']

        if user['length'] < bet:
            await query.edit_message_text("Lo hai troppo piccolo per questo coinflip.")
            return

        user['length'] -= bet
        win = random.choice(["cannetta", "cannone"])
        msg = f"Hai scelto: {choice}\nÈ uscito: {win}\n"

        if choice == win:
            user['length'] += bet * 2
            user['stats']['won'] += 1
            msg += f"💰 HAI VINTO! Guadagni: +{bet}cm, viva il duce"
        else:
            user['stats']['lost'] += 1
            msg += f"💸 Hai perso {bet}cm, sfigato."

        user['stats']['bet_total'] += bet
        del data['duels'][user_id]
        save_data()

        await query.edit_message_text(msg + f"\nOra il tuo cazzo è lungo {user['length']}cm")

    except Exception as e:
        logger.error(f"Errore nel coinflip callback: {e}")
        await query.edit_message_text("Errore nel coinflip!")


async def handle_duel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle duel callback"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, challenger_id = query.data.split(':')[1:3]
        challenger_id = int(challenger_id)
        
        if query.from_user.id == challenger_id:
            await query.edit_message_text("Non puoi accettare il tuo stesso duello ritardato!")
            return
        
        challenger = get_user(challenger_id)
        defender = get_user(query.from_user.id)
        
        if action == "accept":
            # Duel logic
            challenger = get_user(challenger_id)
            defender = get_user(query.from_user.id)

            challenger_bet = data['duels'].get(str(challenger_id), {}).get('bet')
            if challenger_bet is None:
                await query.edit_message_text("Il duello non è valido o è scaduto.")
                return

            if defender['length'] < challenger_bet:
                await query.answer("Lo hai troppo piccolo per accettare il duello!", show_alert=True)
                return
            
            challenger['length'] -= challenger_bet
            defender['length'] -= challenger_bet
            total_pot = challenger_bet + challenger_bet

            winner = random.choice(['challenger', 'defender'])
            if winner == 'challenger':
                challenger['length'] += total_pot
                result = f"{get_username(update.effective_user)} ha corso un rischio ed è stato premiato!\nHa vinto {total_pot}cm!"
            else:
                defender['length'] += total_pot
                result = f"{get_username(query.from_user)} ha le palle, e sono esplose in faccia all'avversario!\nIn cambio vince {total_pot}cm!"

            del data['duels'][str(challenger_id)]
            save_data()
            await query.edit_message_text(result)

            
    except Exception as e:
        logger.error(f"Error in duel callback: {e}")
        await query.edit_message_text("Errore nel duello!")

async def handle_donation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle donation callback - placeholder"""
    query = update.callback_query
    await query.answer("Funzione donazione non ancora implementata!")

# === Background Lottery Thread ===
async def lottery_draw_loop(app):
    logger.info("lottery_draw_loop is running")
    group_id = FIXED_GROUP_CHAT_ID
    while True:
        try:
            await asyncio.sleep(5)  # Check every 5 seconds
            current_time = now()

            with data_lock:
                end_time = data['lottery'].get('end_time', 0)
                if current_time < end_time:
                    continue

                bets = data['lottery']['bets'].copy()
                data['lottery']['end_time'] = current_time + LOTTERY_INTERVAL

            if not bets:
                logger.info("Nessuna scommessa attiva. Nuovo round iniziato.")
                continue

            # Draw time!
            winning_number = random.randint(1, 10)
            logger.info(f"Numero estratto: {winning_number}")

            winning_bets = {
                uid: b for uid, b in bets.items() if b['number'] == winning_number
            }

            total_pot = sum(b['amount'] for b in bets.values())
            total_winning = sum(b['amount'] for b in winning_bets.values())

            logger.info(f"Inviando messaggio al gruppo {group_id}")
            logger.info(f"Inviando messaggio al gruppo {total_pot}")

            group_id = FIXED_GROUP_CHAT_ID
            message = f"🎯 Numero estratto: {winning_number}\n\n"

            logger.info(f"Arrivo anche qua")

            if winning_bets:
                winners = []
                losers = []
                with data_lock:
                    for uid, b in bets.items():
                        user = get_user(uid)
                        name = user.get('username', f'user_{uid}')
                        logger.info(f"Qua si")
                        if uid in winning_bets:
                            share = int(total_pot * (b['amount'] / total_winning))
                            user['length'] += share
                            user['stats']['length_won'] += share
                            winners.append(f"- @{name} ha vinto {share}cm")
                            logger.info(f"Qua pure")
                        else:
                            user['stats']['length_lost'] += b['amount']
                            losers.append(f"- @{name} ha perso {b['amount']}cm")
                            logger.info(f"Qua anche")

                    data['lottery']['bets'] = {}
                    data['lottery']['history'].append(winning_number)
                    data['lottery']['history'] = data['lottery']['history'][-5:]

                message += "🏆 Vincitori:\n" + "\n".join(winners) + "\n\n"
                message += "❌ Perdenti:\n" + "\n".join(losers)

                logger.info(f"E anche qua")

            else:
                logger.info("Nessun vincitore - rimborso in corso")
                with data_lock:
                    for uid, b in bets.items():
                        logger.info(f"Rimborsando utente {uid} con {b['amount']}cm")
            
                        user = get_user(uid)
                        if not isinstance(user, dict):
                            logger.warning(f"Utente {uid} è None o malformato: {user}")
                            continue

                        try:
                            amount = int(b.get('amount', 0))
                            user['length'] += amount
                            logger.info(f"Nuova lunghezza per utente {uid}: {user['length']}")
                        except Exception as e:
                            logger.exception(f"Errore nel rimborso per utente {uid}")

                    message += "😢 Nessun vincitore. Puntate rimborsate."
                    logger.info("Rimborso completato")



            save_data()
            logger.info("Inizio invio messaggio estrazione lotteria")
            if group_id:
                try:
                    logger.info(f"Inviando messaggio al gruppo {group_id}")
                    await app.bot.send_message(chat_id=group_id, text=message)
                    logger.info("✅ Messaggio lotteria inviato con successo")
                except Exception as e:
                    logger.exception("❌ Errore durante invio messaggio lotteria")
            else:
                logger.warning("⚠️ Group chat ID non definito — messaggio non inviato.")


        except Exception as e:
            logger.error(f"Errore nel ciclo lotteria: {e}")
            logger.info(f"Errore nel ciclo lotteria: {e}")
            await asyncio.sleep(10)


# === Error Handler ===
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")


async def post_init(app):
    asyncio.create_task(lottery_draw_loop(app))
    logger.info("Background lottery loop started.")

# === Bot Setup ===
def main():
    """Main function to run the bot"""
    
    # Build application
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    group_id = FIXED_GROUP_CHAT_ID
    logger.info(f"Stored group_chat_id: {group_id}")
    
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
    app.add_handler(CallbackQueryHandler(handle_coinflip_callback, pattern='^coinflip:'))

    
    # Add error handler
    app.add_error_handler(error_handler)
    
    logger.info("Bot started successfully")
    app.run_polling()

if __name__ == '__main__':
    main()
