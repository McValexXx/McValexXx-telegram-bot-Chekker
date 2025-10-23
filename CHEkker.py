import sys
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# 🧩 Asigură afișarea corectă a caracterelor UTF-8 (fără erori în CMD)
sys.stdout.reconfigure(encoding='utf-8')

DATA_FILE = "data.json"


# ===== FUNCȚII DE SALVARE/ÎNCĂRCARE =====
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"lists": {}, "stats": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"lists": {}, "stats": {}}


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Eroare la salvare: {e}")


# ===== COMENZI =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salut! Eu sunt botul de cumpărături al echipei!\n\n"
        "Comenzi disponibile:\n"
        "🛒 /newlist - creează o listă nouă\n"
        "📋 /showlist - afișează lista curentă\n"
        "🗑️ /resetlist - șterge lista curentă\n"
        "📊 /stats - afișează statistica cumpărăturilor\n\n"
        "👉 Pentru a bifa sau debifa un produs, doar apasă pe el!"
    )


async def newlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    chat_id = str(update.effective_chat.id)

    if not context.args:
        await update.message.reply_text(
            "Te rog să introduci lista după comandă.\nEx: /newlist lapte, paine, ouă"
        )
        return

    items = [i.strip() for i in " ".join(context.args).split(",") if i.strip()]
    if not items:
        await update.message.reply_text("Lista nu poate fi goală.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    data["lists"][chat_id] = {
        "items": {item: None for item in items},
        "date": date_str,
    }
    save_data(data)

    keyboard = [
        [InlineKeyboardButton(f"☐ {item}", callback_data=item)] for item in items
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🛒 Listă creată la {date_str}:\nApasă pe produs când l-ai cumpărat 👇",
        reply_markup=reply_markup,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    chat_id = str(query.message.chat_id)
    user = query.from_user.first_name
    item = query.data

    if chat_id not in data["lists"]:
        await query.edit_message_text("Lista nu mai este activă.")
        return

    lst = data["lists"][chat_id]["items"]

    # 🔁 Toggle bifă/debifă
    if lst[item] is None:
        lst[item] = user
        data["stats"][user] = data["stats"].get(user, 0) + 1
    else:
        lst[item] = None
        if user in data["stats"] and data["stats"][user] > 0:
            data["stats"][user] -= 1

    save_data(data)

    # Refacem tastatura
    keyboard = []
    for name, buyer in lst.items():
        mark = "✅" if buyer else "☐"
        label = f"{mark} {name}"
        if buyer:
            label += f" — {buyer}"
        keyboard.append([InlineKeyboardButton(label, callback_data=name)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_reply_markup(reply_markup=reply_markup)

    # 🎉 Mesaj final dacă totul e cumpărat
    if all(v is not None for v in lst.values()):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 Bravo, echipă! Toate produsele au fost cumpărate! 🛍️",
        )


async def showlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    chat_id = str(update.effective_chat.id)

    if chat_id not in data["lists"]:
        await update.message.reply_text("Nu există nicio listă activă.")
        return

    lst = data["lists"][chat_id]["items"]
    date = data["lists"][chat_id]["date"]
    text = f"📋 Listă creată la {date}:\n\n"

    for item, buyer in lst.items():
        status = f"✅ {buyer}" if buyer else "❌"
        text += f"- {item}: {status}\n"

    await update.message.reply_text(text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["stats"]:
        await update.message.reply_text("Nu există date în statistici.")
        return

    sorted_stats = sorted(data["stats"].items(), key=lambda x: x[1], reverse=True)
    text = "📊 Statistica cumpărăturilor:\n\n"
    for user, count in sorted_stats:
        text += f"👤 {user}: {count} produse\n"

    await update.message.reply_text(text)


# 🆕 RESET LISTĂ CU CONFIRMARE
async def resetlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    chat_id = str(update.effective_chat.id)

    if chat_id not in data["lists"]:
        await update.message.reply_text("Nu există nicio listă de șters.")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Da, șterge lista", callback_data="confirm_reset"),
            InlineKeyboardButton("❌ Anulează", callback_data="cancel_reset"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Ești sigur că vrei să ștergi lista curentă?", reply_markup=reply_markup
    )


async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    chat_id = str(query.message.chat_id)

    if query.data == "confirm_reset":
        if chat_id in data["lists"]:
            del data["lists"][chat_id]
            save_data(data)
            await query.edit_message_text("🗑️ Lista a fost ștearsă cu succes.")
            await context.bot.send_message(
                chat_id=chat_id,
                text="🆕 Creează o nouă listă cu comanda:\n`/newlist produs1, produs2, produs3`",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text("Nu există nicio listă de șters.")
    else:
        await query.edit_message_text("❌ Ștergerea listei a fost anulată.")


# ===== MAIN =====
def main():
    TOKEN = os.getenv("BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newlist", newlist))
    app.add_handler(CommandHandler("showlist", showlist))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("resetlist", resetlist))
    app.add_handler(CallbackQueryHandler(reset_handler, pattern="^confirm_reset|cancel_reset$"))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Botul rulează... apasă Ctrl+C pentru oprire.")
    app.run_polling()


if __name__ == "__main__":
    main()
