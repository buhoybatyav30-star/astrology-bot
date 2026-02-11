#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔮 АСТРОЛОГИЧЕСКИЙ БОТ - УЛУЧШЕННАЯ ВЕРСИЯ
✅ Безопасная загрузка токенов из .env
✅ Премиум-гороскопы из внешней базы (365 дней × 12 знаков)
✅ Бесплатные гороскопы — короткие, премиум — развернутые
✅ Потокобезопасная БД с блокировкой
"""

import logging
import random
import json
import os
import hashlib
import uuid
import asyncio
from datetime import datetime, timedelta
from threading import Lock
from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    PreCheckoutQueryHandler
)

# ====== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ======
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ ОШИБКА: Не задан BOT_TOKEN в .env файле!")
if not PAYMENT_PROVIDER_TOKEN:
    raise ValueError("❌ ОШИБКА: Не задан PAYMENT_PROVIDER_TOKEN в .env файле!")

# Создаем папки
os.makedirs('data', exist_ok=True)

# ====== НАСТРОЙКА ЛОГИРОВАНИЯ ======
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/astrology_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

print("=" * 70)
print("🔮 АСТРОЛОГИЧЕСКИЙ БОТ - УЛУЧШЕННАЯ ВЕРСИЯ")
print(f"✅ Токен бота загружен: {BOT_TOKEN[:10]}...")
print(f"✅ Платежный токен загружен: {PAYMENT_PROVIDER_TOKEN[:20]}...")
print("=" * 70)

# ====== ЗАГРУЗКА БАЗЫ ПРЕМИУМ ГОРОСКОПОВ ======
PREMIUM_HOROSCOPES = {}
if os.path.exists('horoscopes_premium.json'):
    try:
        with open('horoscopes_premium.json', 'r', encoding='utf-8') as f:
            PREMIUM_HOROSCOPES = json.load(f)
        logger.info(f"✅ Загружено {len(PREMIUM_HOROSCOPES)} дней премиум-гороскопов")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки гороскопов: {e}")
else:
    logger.warning("⚠️ Файл horoscopes_premium.json не найден. Используются базовые шаблоны.")

# ====== БАЗА ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ ======
class UserDatabase:
    def __init__(self, filename='data/users.json'):
        self.filename = filename
        self.lock = Lock()
        self.data = self.load_data()
    
    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key in ['users', 'premium', 'payments', 'stats']:
                        if key not in data:
                            data[key] = {}
                    return data
            except Exception as e:
                logger.error(f"Ошибка загрузки БД: {e}")
        return {k: {} for k in ['users', 'premium', 'payments', 'stats']}
    
    def save_data(self):
        try:
            with self.lock:
                with open(self.filename, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения БД: {e}")
    
    # ... остальные методы БД (оставлены без изменений для краткости)
    # [Полная реализация методов из предыдущего кода: add_user, get_user, update_counter, 
    #  add_premium, is_premium, save_payment, update_payment_status, update_user_birth_date, get_all_users_stats]

def get_all_users_stats(self):
    """Получение статистики по всем пользователям"""
    try:
        total_users = len(self.data.get('users', {}))
        premium_users = len(self.data.get('premium', {}))
        total_payments = len(self.data.get('payments', {}))
        
        successful_payments = 0
        total_revenue = 0
        for payment in self.data.get('payments', {}).values():
            if payment.get('status') == 'succeeded':
                successful_payments += 1
                total_revenue += float(payment.get('amount', 0))
        
        total_horoscopes = sum(u.get('horoscope_count', 0) for u in self.data.get('users', {}).values())
        total_numerology = sum(u.get('num_count', 0) for u in self.data.get('users', {}).values())
        total_tarot = sum(u.get('tarot_count', 0) for u in self.data.get('users', {}).values())
        total_compatibility = sum(u.get('compatibility_count', 0) for u in self.data.get('users', {}).values())
        
        return {
            'total_users': total_users,
            'premium_users': premium_users,
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'total_horoscopes': total_horoscopes,
            'total_numerology': total_numerology,
            'total_tarot': total_tarot,
            'total_compatibility': total_compatibility,
            'total_revenue': total_revenue
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return {
            'total_users': 0,
            'premium_users': 0,
            'total_payments': 0,
            'successful_payments': 0,
            'total_horoscopes': 0,
            'total_numerology': 0,
            'total_tarot': 0,
            'total_compatibility': 0,
            'total_revenue': 0
        }
# Инициализация БД
db = UserDatabase()

# ====== БИБЛИОТЕКА ИЗОБРАЖЕНИЙ ======
ZODIAC_IMAGES = {
    "♈️ Овен": "https://img.icons8.com/color/512/aries.png",
    "♉️ Телец": "https://img.icons8.com/color/512/taurus.png",
    "♊️ Близнецы": "https://img.icons8.com/color/512/gemini.png",
    "♋️ Рак": "https://img.icons8.com/color/512/cancer.png",
    "♌️ Лев": "https://img.icons8.com/color/512/leo.png",
    "♍️ Дева": "https://img.icons8.com/color/512/virgo.png",
    "♎️ Весы": "https://img.icons8.com/color/512/libra.png",
    "♏️ Скорпион": "https://img.icons8.com/color/512/scorpio.png",
    "♐️ Стрелец": "https://img.icons8.com/color/512/sagittarius.png",
    "♑️ Козерог": "https://img.icons8.com/color/512/capricorn.png",
    "♒️ Водолей": "https://img.icons8.com/color/512/aquarius.png",
    "♓️ Рыбы": "https://img.icons8.com/color/512/pisces.png"
}

TAROT_IMAGES = {
    "Шут": "https://img.icons8.com/color/512/jester.png",
    "Маг": "https://img.icons8.com/color/512/wizard.png",
    "Верховная Жрица": "https://img.icons8.com/color/512/queen.png",
    "Императрица": "https://img.icons8.com/color/512/empress.png",
    "Император": "https://img.icons8.com/color/512/king.png",
    "Иерофант": "https://img.icons8.com/color/512/priest.png",
    "Влюбленные": "https://img.icons8.com/color/512/couple.png",
    "Колесница": "https://img.icons8.com/color/512/chariot.png",
    "Сила": "https://img.icons8.com/color/512/strength.png",
    "Отшельник": "https://img.icons8.com/color/512/hermit.png"
}

# ====== УЛУЧШЕННАЯ ГЕНЕРАЦИЯ ГОРОСКОПОВ ======
def get_current_date_string():
    months = {1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
              7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"}
    now = datetime.now()
    weekday = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"][now.weekday()]
    return f"{now.day} {months[now.month]} {now.year} года ({weekday})"

def generate_basic_horoscope(zodiac_sign, user_id=None):
    """Базовый гороскоп для бесплатных пользователей (короткий)"""
    today = datetime.now().strftime("%Y-%m-%d")
    seed_string = f"{today}_{user_id}_{zodiac_sign}" if user_id else f"{today}_{zodiac_sign}"
    seed_hash = hashlib.md5(seed_string.encode()).hexdigest()
    seed_number = int(seed_hash[:8], 16)
    random.seed(seed_number)
    
    date_str = get_current_date_string()
    
    horoscope = f"""✨ *Гороскоп для {zodiac_sign}* ✨
*На {date_str}*

{random.choice([
    "День благоприятствует новым начинаниям. Действуйте смело!",
    "Энергия дня способствует гармонии и внутреннему покою.",
    "Доверяйте интуиции при принятии решений сегодня.",
    "Неожиданная встреча может изменить ваш день к лучшему."
])}

💖 *Любовь:* {random.choice(['Романтические моменты ждут вас сегодня', 'Глубокие разговоры укрепят отношения', 'Будьте открыты новым знакомствам'])}

💼 *Карьера:* {random.choice(['Финансовые возможности активизируются', 'Коллеги окажут поддержку в важном деле', 'Смелые решения принесут плоды'])}

🌿 *Здоровье:* {random.choice(['Прогулка на свежем воздухе восстановит силы', 'Обратите внимание на режим сна', 'Йога или медитация принесут гармонию'])}

💫 *Совет:* {random.choice(['Будьте гибкими в решениях', 'Отпустите контроль над ситуацией', 'Проявите терпение — всё придет вовремя'])}

#{zodiac_sign.split()[-1]} #Астрология #Гороскоп"""
    
    random.seed(datetime.now().timestamp())
    return horoscope

def generate_premium_horoscope(zodiac_sign, user_id=None):
    """Премиум гороскоп из базы (полный, разнообразный)"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Пытаемся взять из базы
    if today in PREMIUM_HOROSCOPES and zodiac_sign in PREMIUM_HOROSCOPES[today]:
        return PREMIUM_HOROSCOPES[today][zodiac_sign]
    
    # Если нет в базе — генерируем расширенный
    return generate_basic_horoscope(zodiac_sign, user_id) + """

✨ *ПРЕМИУМ ДОПОЛНЕНИЕ* ✨

*Астрологические детали:*
• Луна в знаке: {moon_sign}
• Благоприятное время: {lucky_time}
• Камень-талисман: {stone}
• Цвет удачи: {color}

*Недельный прогноз:*
{weekly_forecast}

#Премиум""".format(
    moon_sign=random.choice(['Овна', 'Тельца', 'Близнецов', 'Рака', 'Льва', 'Девы', 'Весов', 'Скорпиона', 'Стрельца', 'Козерога', 'Водолея', 'Рыб']),
    lucky_time=random.choice(['утро 9-11', 'день 14-16', 'вечер 19-21']),
    stone=random.choice(['аметист', 'горный хрусталь', 'розовый кварц', 'лазурит', 'тигровый глаз', 'цитрин']),
    color=random.choice(['золотой', 'изумрудный', 'сапфировый', 'рубиновый', 'лавандовый']),
    weekly_forecast=random.choice([
        'Неделя принесет важные переговоры и новые возможности для роста.',
        'Финансовая сфера будет особенно благоприятной в середине недели.',
        'Отличное время для творческих проектов и самовыражения.'
    ])
)

# ====== ОСНОВНЫЕ ОБРАБОТЧИКИ (сокращены для краткости) ======
# [Все обработчики из предыдущего кода: start, handle_main_menu, handle_zodiac_selection,
#  handle_numerology_input, handle_tarot_callback, handle_tarot_daily, handle_tarot_three,
#  handle_premium_callback, pre_checkout_handler, successful_payment_handler,
#  handle_back_callback, error_handler]

async def handle_zodiac_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора знака зодиака с разными гороскопами для премиум/бесплатных"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "🔙 Назад в меню":
        await update.message.reply_text("🔙 Возвращаемся в главное меню:", reply_markup=get_main_keyboard(user_id))
        return
    
    zodiac_sign = text
    
    if zodiac_sign in ZODIAC_IMAGES:
        try:
            is_premium = db.is_premium(user_id)
            db.update_counter(user_id, 'horoscope_count')
            
            await update.message.reply_text(f"🔮 *Генерирую гороскоп для {zodiac_sign}...* ✨", parse_mode='Markdown')
            
            # Выбираем тип гороскопа
            if is_premium:
                horoscope = generate_premium_horoscope(zodiac_sign, user_id)
            else:
                horoscope = generate_basic_horoscope(zodiac_sign, user_id)
            
            # Отправляем изображение
            try:
                await update.message.reply_photo(photo=ZODIAC_IMAGES[zodiac_sign], caption=f"✨ {zodiac_sign} ✨")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Не удалось отправить изображение: {e}")
            
            # Отправляем гороскоп
            await update.message.reply_text(horoscope, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка генерации гороскопа: {e}")
            await update.message.reply_text(f"✨ *Гороскоп для {zodiac_sign}* ✨\n\nСегодня звезды благоприятствуют вам!", reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
    else:
        await update.message.reply_text("🔮 Выбери знак зодиака из меню!", reply_markup=get_zodiac_keyboard())

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (клавиатуры) ======
def get_main_keyboard(user_id=None):
    is_premium = db.is_premium(user_id) if user_id else False
    keyboard = [
        ["🔮 Гороскоп", "🔢 Нумерология"],
        ["🃏 Таро", "⭐ Премиум активен" if is_premium else "💎 Премиум"],
        ["📊 Статистика", "ℹ️ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_zodiac_keyboard():
    keyboard = [
        ["♈️ Овен", "♉️ Телец", "♊️ Близнецы"],
        ["♋️ Рак", "♌️ Лев", "♍️ Дева"],
        ["♎️ Весы", "♏️ Скорпион", "♐️ Стрелец"],
        ["♑️ Козерог", "♒️ Водолей", "♓️ Рыбы"],
        ["🔙 Назад в меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_premium_keyboard():
    keyboard = [
        [InlineKeyboardButton("💎 1 месяц - 299₽", callback_data="premium_1")],
        [InlineKeyboardButton("💎 3 месяца - 799₽", callback_data="premium_3")],
        [InlineKeyboardButton("💎 12 месяцев - 1999₽", callback_data="premium_12")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_tarot_keyboard():
    keyboard = [
        [InlineKeyboardButton("🃏 Карта дня", callback_data="tarot_daily")],
        [InlineKeyboardButton("🃏 3 карты", callback_data="tarot_three")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ====== ЗАПУСК БОТА ======
def main():
    print("=" * 70)
    print("🔮 ЗАПУСК АСТРОЛОГИЧЕСКОГО БОТА")
    print("=" * 70)
    
    stats = db.get_all_users_stats()
    print(f"📊 Пользователей: {stats['total_users']}")
    print(f"💎 Премиум: {stats['premium_users']}")
    print(f"💰 Платежей: {stats['total_payments']}")
    print("=" * 70)
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрация обработчиков (полная версия как в предыдущем коде)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", start))
        app.add_handler(MessageHandler(filters.Regex(r'^(🔮 Гороскоп|🔢 Нумерология|🃏 Таро|💎 Премиум|⭐ Премиум активен|📊 Статистика|ℹ️ Помощь)$'), handle_main_menu))
        app.add_handler(MessageHandler(filters.Regex(r'^(♈️ Овен|♉️ Телец|♊️ Близнецы|♋️ Рак|♌️ Лев|♍️ Дева|♎️ Весы|♏️ Скорпион|♐️ Стрелец|♑️ Козерог|♒️ Водолей|♓️ Рыбы|🔙 Назад в меню)$'), handle_zodiac_selection))
        app.add_handler(MessageHandler(filters.Regex(r'^\d{2}\.\d{2}\.\d{4}$'), handle_numerology_input))
        app.add_handler(CallbackQueryHandler(handle_tarot_callback, pattern="^tarot_"))
        app.add_handler(CallbackQueryHandler(handle_premium_callback, pattern="^premium_"))
        app.add_handler(CallbackQueryHandler(handle_back_callback, pattern="^back_"))
        app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
        app.add_error_handler(error_handler)
        
        print("✅ Бот запущен и готов к работе!")
        print("📱 Напишите /start в Telegram")
        print("=" * 70)
        
        app.run_polling(poll_interval=1, timeout=30, drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА ЗАПУСКА: {e}")
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")

if __name__ == "__main__":
    main()
