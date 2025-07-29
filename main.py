# -*- coding: utf-8 -*-
"""Telegram Expense Bot (v.1.3.5) - Бот работает 24/7 в облаке
v.1.3.1 рабочая версия с компа (запуск через PyCharm)
v.1.3.5 рабочая версия Telegram-бота на сервере,
чтобы он работал постоянно, даже при выключенном компьютере.
Один из самых удобных бесплатных способов — платформа Railway.
реализованы кнопки «Переименовать», «Удалить», «Назад» 
29.07.25(v.1.3.5) добавлена # === АНТИСПАМ ЗАЩИТА ===
"""

import telebot
from telebot import types
import gspread
import os
import json
from io import StringIO
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# Авторизация в Google Sheets через переменную среды GOOGLE_CREDENTIALS
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    creds_dict = json.load(StringIO(GOOGLE_CREDENTIALS))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SPREADSHEET_ID)
    data_sheet = sheet.worksheet("Данные")
    cat_sheet = sheet.worksheet("Категории")
except Exception as e:
    print("Ошибка авторизации или доступа к листам:", e)
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_state = {}

BASE_CATEGORIES = {
    "Еда": ["Продукты", "Кафе"],
    "Проезд": ["Метро", "Такси"],
    "Связь": ["Мобильный", "Интернет"],
    "Оплата КУ": ["Электричество", "Вода", "Газ"],
    "Развлечения": ["Кино", "Игры", "Отдых"]
}

def initialize_categories():
    existing = cat_sheet.get_all_values()
    if len(existing) <= 1:
        for cat, subs in BASE_CATEGORIES.items():
            for sub in subs:
                cat_sheet.append_row([cat, sub])

initialize_categories()

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💸 Расход"),
        types.KeyboardButton("💰 Доход"),
        types.KeyboardButton("📂 Категории"),
        types.KeyboardButton("📊 Отчёт"),
        types.KeyboardButton("⚙ Управление")
    )
    bot.send_message(
        message.chat.id,
        "Привет! Я бот для учёта расходов и доходов.\nВыберите действие кнопками или используйте команды:\n/расход — внести расход\n/доход — внести доход\n/категории — список категорий\n/переименовать — переименование\n/удалить — удалить\n/отчёт [год-месяц] — отчёт за месяц",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text in ["💸 Расход", "/расход"])
def start_expense(message):
    start_transaction(message, "расход")

@bot.message_handler(func=lambda message: message.text in ["💰 Доход", "/доход"])
def start_income(message):
    start_transaction(message, "доход")

def start_transaction(message, type_):
    chat_id = message.chat.id
    categories = list(set([row[0] for row in cat_sheet.get_all_values()[1:] if row[0]]))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat in categories:
        markup.add(cat)
    markup.add("➕ Новая категория")
    user_state[chat_id] = {"step": "category", "type": type_}
    bot.send_message(chat_id, "Выберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📂 Категории")
def show_categories_button(message):
    show_all_categories(message)

@bot.message_handler(func=lambda message: message.text.startswith("📊 Отчёт"))
def report_button(message):
    from datetime import datetime
    current_month = datetime.now().strftime("%Y-%m")
    message.text = f"/отчёт {current_month}"
    monthly_report(message)

@bot.message_handler(func=lambda message: message.text == "⚙ Управление")
def show_manage_options(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    markup.add("Переименовать", "Удалить", "🔙 Назад")
    bot.send_message(message.chat.id, "Что вы хотите сделать?", reply_markup=markup)

RENAME_MODE = "rename"
DELETE_MODE = "delete"

@bot.message_handler(func=lambda message: message.text == "Переименовать")
def rename_category_step1(message):
    user_state[message.chat.id] = {"step": RENAME_MODE}
    bot.send_message(message.chat.id, "Введите название категории, которую хотите переименовать:")

@bot.message_handler(func=lambda message: message.text == "Удалить")
def delete_category_step1(message):
    user_state[message.chat.id] = {"step": DELETE_MODE}
    bot.send_message(message.chat.id, "Введите название категории, которую хотите удалить:")

@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def go_back(message):
    send_welcome(message)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    chat_id = message.chat.id
    state = user_state.get(chat_id)
    if not state:
        return

    step = state["step"]

    if state["step"] == RENAME_MODE:
        old_name = message.text.strip()
        state["old_name"] = old_name
        bot.send_message(chat_id, f"Введите новое имя для категории '{old_name}':")
        state["step"] = "rename_to"
        return

    elif state["step"] == "rename_to":
        new_name = message.text.strip()
        old_name = state["old_name"]
        all_rows = cat_sheet.get_all_values()
        cat_sheet.clear()
        cat_sheet.append_row(["Категория", "Подкатегория"])  # заголовки
        for row in all_rows[1:]:
            row[0] = new_name if row[0] == old_name else row[0]
            cat_sheet.append_row(row)
        bot.send_message(chat_id, f"✅ Категория '{old_name}' переименована в '{new_name}'.")
        user_state.pop(chat_id, None)
        return

    elif state["step"] == DELETE_MODE:
        to_delete = message.text.strip()
        all_rows = cat_sheet.get_all_values()
        new_rows = [r for r in all_rows[1:] if r[0] != to_delete]
        cat_sheet.clear()
        cat_sheet.append_row(["Категория", "Подкатегория"])
        for row in new_rows:
            cat_sheet.append_row(row)
        bot.send_message(chat_id, f"🗑 Категория '{to_delete}' удалена.")
        user_state.pop(chat_id, None)
        return

    
    if step == "category":
        if message.text == "➕ Новая категория":
            bot.send_message(chat_id, "Введите название новой категории:")
            state["step"] = "new_category"
        else:
            state["category"] = message.text
            show_subcategories(chat_id, message.text)

    elif step == "new_category":
        category = message.text.strip()
        cat_sheet.append_row([category, ""])
        state["category"] = category
        bot.send_message(chat_id, f"Категория '{category}' добавлена.")
        show_subcategories(chat_id, category)

    elif step == "subcategory":
        if message.text == "➕ Новая подкатегория":
            bot.send_message(chat_id, "Введите название новой подкатегории:")
            state["step"] = "new_subcategory"
        else:
            state["subcategory"] = message.text
            bot.send_message(chat_id, "Введите сумму:")
            state["step"] = "amount"

    elif step == "new_subcategory":
        subcategory = message.text.strip()
        cat_sheet.append_row([state["category"], subcategory])
        state["subcategory"] = subcategory
        bot.send_message(chat_id, f"Подкатегория '{subcategory}' добавлена.\nВведите сумму:")
        state["step"] = "amount"

    elif step == "amount":
        try:
            amount = float(message.text.strip())
            now = datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            year = now.strftime("%Y")
            month = now.strftime("%Y-%m")
            user = message.from_user.username or message.from_user.first_name
            data_sheet.append_row([
                now_str,
                year,
                month,
                state.get("type", "расход"),
                amount,
                state["category"],
                state["subcategory"],
                user
            ])
            bot.send_message(chat_id, f"✅ {state['type'].capitalize()} {amount}₽ в категории '{state['category']} / {state['subcategory']}' добавлен.")
        except ValueError:
            bot.send_message(chat_id, "❗ Введите сумму числом, например: 250")
        finally:
            user_state.pop(chat_id, None)

def show_subcategories(chat_id, category):
    rows = cat_sheet.get_all_values()[1:]
    subcategories = [r[1] for r in rows if r[0] == category and r[1]]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for sub in subcategories:
        markup.add(sub)
    markup.add("➕ Новая подкатегория")
    user_state[chat_id]["step"] = "subcategory"
    bot.send_message(chat_id, "Выберите подкатегорию:", reply_markup=markup)

def show_all_categories(message):
    rows = cat_sheet.get_all_values()[1:]
    if not rows:
        bot.send_message(message.chat.id, "Категорий пока нет.")
        return

    categories = {}
    for cat, sub in rows:
        if cat not in categories:
            categories[cat] = []
        if sub:
            categories[cat].append(sub)

    text = "📂 <b>Категории и подкатегории:</b>\n"
    for cat, subs in categories.items():
        text += f"\n<b>{cat}</b>"
        if subs:
            text += f": {', '.join(subs)}"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

def monthly_report(message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❗ Используйте формат: /отчёт 2025-07")
        return

    month = parts[1]
    rows = data_sheet.get_all_values()[1:]
    filtered = [r for r in rows if r[2] == month]

    if not filtered:
        bot.send_message(message.chat.id, f"Нет данных за {month}")
        return

    expenses = {}
    incomes = {}

    for r in filtered:
        type_, amount, cat, sub = r[3], float(r[4]), r[5], r[6]
        if type_ == "расход":
            key = f"{cat} / {sub}"
            expenses[key] = expenses.get(key, 0) + amount
        else:
            key = f"{cat} / {sub}"
            incomes[key] = incomes.get(key, 0) + amount

    def format_block(title, data):
        if not data:
            return f"{title}: нет записей"
        lines = [f"{k}: {round(v, 2)}₽" for k, v in data.items()]
        total = sum(data.values())
        return f"{title}:\n" + "\n".join(lines) + f"\nИтого: {round(total, 2)}₽"

    report = f"📊 <b>Отчёт за {month}</b>\n\n"
    report += format_block("💸 Расходы", expenses) + "\n\n"
    report += format_block("💰 Доходы", incomes)

    bot.send_message(message.chat.id, report, parse_mode="HTML")
    
# === АНТИСПАМ ЗАЩИТА ===

ALLOWED_USERS = [123456789]  # ← здесь ваш user_id

SPAM_KEYWORDS = ["airdrop", "freeether", "claim eth", "giveaway", "http://", "https://"]

def is_spam(message):
    text = message.text.lower()
    return any(keyword in text for keyword in SPAM_KEYWORDS)

@bot.message_handler(func=lambda message: True)
def main_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    print(f"[{datetime.now()}] {user_id} ({username}): {message.text}")

    # 🔐 Проверка: только разрешённые пользователи
    if user_id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔ Доступ запрещён.")
        return

    # 🚫 Проверка на спам
    if is_spam(message):
        bot.send_message(message.chat.id, "🚫 Сообщение заблокировано как подозрительное.")
        return

    # ✅ Если всё чисто — обработка
    handle_text(message)

# === ЗАПУСК БОТА ===
bot.polling()

