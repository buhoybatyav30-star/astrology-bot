#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔮 АСТРОЛОГИЧЕСКИЙ БОТ - ГАРАНТИРОВАННО РАБОЧАЯ ВЕРСИЯ
✅ Проверено на Python 3.11.11 + python-telegram-bot==20.7
✅ Без синтаксических ошибок
✅ Без Updater
✅ Готов к работе на Render
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
print("🔮 АСТРОЛОГИЧЕСКИЙ БОТ - ГАРАНТИРОВАННО РАБОЧАЯ ВЕРСИЯ")
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
    
    def add_user(self, user_id, username, first_name):
        user_id_str = str(user_id)
        if user_id_str not in self.data['users']:
            self.data['users'][user_id_str] = {
                'username': username or 'unknown',
                'first_name': first_name or 'Пользователь',
                'joined': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'horoscope_count': 0,
                'num_count': 0,
                'tarot_count': 0,
                'compatibility_count': 0,
                'last_zodiac': None,
                'last_horoscope_date': None,
                'chat_id': user_id,
                'birth_date': None,
                'life_path_number': None,
                'total_requests': 0
            }
            self.save_data()
            logger.info(f"👤 Новый пользователь: {user_id} ({first_name})")
    
    def get_user(self, user_id):
        return self.data['users'].get(str(user_id))
    
    def update_counter(self, user_id, counter_name):
        user_id_str = str(user_id)
        if user_id_str not in self.data['users']:
            self.add_user(user_id, None, None)
        if counter_name not in self.data['users'][user_id_str]:
            self.data['users'][user_id_str][counter_name] = 0
        self.data['users'][user_id_str][counter_name] += 1
        self.data['users'][user_id_str]['total_requests'] = self.data['users'][user_id_str].get('total_requests', 0) + 1
        self.save_data()
    
    def add_premium(self, user_id, days):
        user_id_str = str(user_id)
        end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        self.data['premium'][user_id_str] = end_date
        self.save_data()
        logger.info(f"💎 Премиум активирован для {user_id} на {days} дней (до {end_date})")
        return end_date
    
    def is_premium(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data['premium']:
            date_str = self.data['premium'][user_id_str]
            try:
                try:
                    end_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        end_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        del self.data['premium'][user_id_str]
                        self.save_data()
                        return False
                if end_date > datetime.now():
                    return True
                else:
                    del self.data['premium'][user_id_str]
                    self.save_data()
                    return False
            except Exception as e:
                logger.error(f"Ошибка проверки премиума {user_id}: {e}")
                return False
        return False
    
    def save_payment(self, payment_id, user_id, tariff_days, amount, status='pending'):
        try:
            if 'payments' not in self.data:
                self.data['payments'] = {}
            payment_record = {
                'user_id': str(user_id),
                'tariff_days': tariff_days,
                'amount': amount,
                'status': status,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self.data['payments'][payment_id] = payment_record
            self.save_data()
            logger.info(f"💰 Платеж сохранен: {payment_id} | Пользователь: {user_id} | Сумма: {amount}₽ | Статус: {status}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения платежа: {e}")
    
    def update_payment_status(self, payment_id, status):
        try:
            if 'payments' in self.data and payment_id in self.data['payments']:
                self.data['payments'][payment_id]['status'] = status
                self.data['payments'][payment_id]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.save_data()
                logger.info(f"🔄 Статус платежа {payment_id} обновлен на: {status}")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса платежа: {e}")
    
    def update_user_birth_date(self, user_id, birth_date, life_path):
        user_id_str = str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['birth_date'] = birth_date
            self.data['users'][user_id_str]['life_path_number'] = life_path
            self.save_data()
    
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
    
    if today in PREMIUM_HOROSCOPES and zodiac_sign in PREMIUM_HOROSCOPES[today]:
        return PREMIUM_HOROSCOPES[today][zodiac_sign]
    
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

# ====== ОСНОВНЫЕ ОБРАБОТЧИКИ ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    try:
        db.add_user(user_id, user.username, user.first_name)
        is_premium = db.is_premium(user_id)
        welcome_text = f"""✨ *Добро пожаловать, {user.first_name}!* 🔮

Я твой личный астрологический помощник!

{'✅ **ВАШ ПРЕМИУМ АКТИВЕН!**' if is_premium else '✨ *Попробуй все возможности бота!*'}

*Доступные услуги:*
• 🔮 Уникальные гороскопы (разные каждый день!)
• 🔢 Нумерология по дате рождения
• 🃏 Гадание на Таро
• 💎 Премиум подписка

Выбери услугу из меню ниже 👇"""
        await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /start: {e}")
        await update.message.reply_text("Привет! Добро пожаловать в астрологический бот! 🔮", reply_markup=get_main_keyboard())

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    try:
        is_premium = db.is_premium(user_id)
        if text == "🔮 Гороскоп":
            await update.message.reply_text(f"🔮 *Гороскоп на {get_current_date_string()}*\n\nВыбери свой знак зодиака:", reply_markup=get_zodiac_keyboard(), parse_mode='Markdown')
        elif text == "🔢 Нумерология":
            await update.message.reply_text("🔢 *Нумерологический анализ*\n\nВведи дату рождения в формате:\n`ДД.ММ.ГГГГ`\n\n*Например:* `23.09.1992`", parse_mode='Markdown')
        elif text == "🃏 Таро":
            if is_premium:
                await update.message.reply_text("🃏 *Гадание на Таро*\n\nВыбери тип расклада:", reply_markup=get_tarot_keyboard(), parse_mode='Markdown')
            else:
                await update.message.reply_text("🃏 *Гадание на Таро*\n\n❌ *Требуется премиум подписка!*\n\nОформи премиум для доступа к Таро! 💎", reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
        elif text == "💎 Премиум" or text == "⭐ Премиум активен":
            await update.message.reply_text(f"""💎 *ПРЕМИУМ ПОДПИСКА*

{'✅ **ВАШ ПРЕМИУМ АКТИВЕН!**' if is_premium else '❌ **ПРЕМИУМ НЕ АКТИВЕН**'}

*Полный доступ ко всем функциям:*

✨ **РАСШИРЕННЫЕ ГОРОСКОПЫ**
• Детальный астрологический анализ
• Недельные прогнозы
• Персональные рекомендации

🃏 **ГАДАНИЕ НА ТАРО**
• Карта дня с изображением
• Расклад на 3 карты
• Все карты с картинками

🔢 **ПРОФЕССИОНАЛЬНАЯ НУМЕРОЛОГИЯ**
• Полный анализ чисел
• Кармические задачи
• Рекомендации по развитию

Выбери тариф:""", reply_markup=get_premium_keyboard(), parse_mode='Markdown')
        elif text == "📊 Статистика":
            user_info = db.get_user(user_id)
            if user_info:
                stats_text = f"""📊 *ЛИЧНАЯ СТАТИСТИКА*

👤 *Пользователь:* {user_info.get('first_name', 'Гость')}
📅 *Регистрация:* {user_info.get('joined', 'Неизвестно')}
💎 *Премиум:* {'✅ Активен' if is_premium else '❌ Не активен'}

*📈 ИСПОЛЬЗОВАНО УСЛУГ:*
🔮 Гороскопы: {user_info.get('horoscope_count', 0)}
🔢 Нумерология: {user_info.get('num_count', 0)}
🃏 Таро: {user_info.get('tarot_count', 0)}"""
            else:
                stats_text = "📊 *Вы ещё не использовали услуги бота.*"
            await update.message.reply_text(stats_text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
        elif text == "ℹ️ Помощь":
            help_text = """ℹ️ *ПОМОЩЬ И ИНФОРМАЦИЯ*

*Команды бота:*
/start - Главное меню
/help - Эта справка

*Доступные услуги:*
• 🔮 Ежедневные гороскопы
• 🔢 Нумерология
• 🃏 Гадание на Таро (премиум)
• 💎 Премиум подписка

*💫 Все предсказания носят развлекательный характер*"""
            await update.message.reply_text(help_text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
        elif text == "🔙 Назад в меню":
            await update.message.reply_text("🔙 Возвращаемся в главное меню:", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"❌ Ошибка в главном меню: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.", reply_markup=get_main_keyboard(user_id))

async def handle_zodiac_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            if is_premium:
                horoscope = generate_premium_horoscope(zodiac_sign, user_id)
            else:
                horoscope = generate_basic_horoscope(zodiac_sign, user_id)
            try:
                await update.message.reply_photo(photo=ZODIAC_IMAGES[zodiac_sign], caption=f"✨ {zodiac_sign} ✨")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Не удалось отправить изображение: {e}")
            await update.message.reply_text(horoscope, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка генерации гороскопа: {e}")
            await update.message.reply_text(f"✨ *Гороскоп для {zodiac_sign}* ✨\n\nСегодня звезды благоприятствуют вам!", reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
    else:
        await update.message.reply_text("🔮 Выбери знак зодиака из меню!", reply_markup=get_zodiac_keyboard())

async def handle_numerology_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    try:
        date_obj = datetime.strptime(text, '%d.%m.%Y')
        day, month, year = date_obj.day, date_obj.month, date_obj.year
        db.update_counter(user_id, 'num_count')
        await update.message.reply_text("🔢 *Анализирую ваши числа...* ✨", parse_mode='Markdown')
        
        life_path = sum(int(d) for d in str(day + month + year))
        while life_path > 9:
            life_path = sum(int(d) for d in str(life_path))
        
        personalities = [
            "**ЛИДЕР И НОВАТОР** 💪\nВы рождены, чтобы вести за собой.",
            "**ДИПЛОМАТ И МИРОТВОРЕЦ** 🤝\nВаш дар - находить гармонию.",
            "**ТВОРЕЦ И ОПТИМИСТ** 🎨\nВы приносите в мир красоту и радость.",
            "**СТРОИТЕЛЬ И ПРАКТИК** 🏗️\nВы создаёте прочный фундамент.",
            "**ИССЛЕДОВАТЕЛЬ И АВАНТЮРИСТ** 🌍\nВаша стихия - свобода и движение."
        ]
        
        advice_options = [
            "Доверяйте своему внутреннему голосу.",
            "Используйте свои сильные стороны для достижения целей.",
            "Работайте над своими слабостями, превращая их в возможности."
        ]
        
        numerology_result = f"""🔢 *НУМЕРОЛОГИЧЕСКИЙ ПОРТРЕТ*

*Дата рождения:* {text}
*Число жизненного пути:* {life_path}

{random.choice(personalities)}

*💫 Совет:*
{random.choice(advice_options)}"""
        
        await update.message.reply_text(numerology_result, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("❌ *Неверный формат даты!*\n\nИспользуй: `ДД.ММ.ГГГГ`\n*Пример:* `23.09.1992`", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Ошибка нумерологии: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.", reply_markup=get_main_keyboard(user_id))

async def handle_tarot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        if not db.is_premium(user_id):
            await query.message.reply_text("❌ *Требуется премиум подписка!*", reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
            return
        spread_type = query.data
        db.update_counter(user_id, 'tarot_count')
        if spread_type == "tarot_daily":
            await handle_tarot_daily(update, context, user_id)
        elif spread_type == "tarot_three":
            await handle_tarot_three(update, context, user_id)
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике Таро: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте еще раз.", reply_markup=get_main_keyboard(user_id))

async def handle_tarot_daily(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    query = update.callback_query
    card_name = random.choice(list(TAROT_IMAGES.keys()))
    card_image = TAROT_IMAGES[card_name]
    is_reversed = random.choice([True, False])
    try:
        await query.message.reply_photo(photo=card_image, caption=f"🃏 *{card_name}* ({'перевернутая' if is_reversed else 'прямая'})")
    except Exception as img_error:
        logger.warning(f"⚠️ Не удалось отправить изображение карты: {img_error}")
    tarot_text = f"""🃏 *КАРТА ДНЯ*

*Выпала карта:*
**{card_name}** ({'перевернутая' if is_reversed else 'прямая'})

*📖 Значение:*
{random.choice([
    "Эта карта указывает на важность вашего внутреннего голоса.",
    "Сегодняшний день несет ключевое сообщение для вашего развития.",
    "Карта предлагает обратить внимание на определенную сферу жизни."
])}

*🎯 Совет карты:*
{random.choice([
    "Доверьтесь вселенной и следуйте за своим любопытством.",
    "Используйте все доступные вам ресурсы для достижения целей.",
    "Прислушивайтесь к своему внутреннему голосу и подсознанию."
])}"""
    await query.message.reply_text(tarot_text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')

async def handle_tarot_three(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    query = update.callback_query
    cards = random.sample(list(TAROT_IMAGES.items()), 3)
    for card_name, card_image in cards:
        try:
            await query.message.reply_photo(photo=card_image, caption=f"🃏 *{card_name}*")
            await asyncio.sleep(0.5)
        except Exception as img_error:
            logger.warning(f"⚠️ Не удалось отправить изображение: {img_error}")
    tarot_text = f"""🃏 *РАСКЛАД НА 3 КАРТЫ*

*Прошлое (влияние на текущую ситуацию):*
**{cards[0][0]}**
{random.choice([
    "Ваш прошлый опыт подготовил вас к текущей ситуации.",
    "Прошлые события продолжают влиять на вашу жизнь."
])}

*Настоящее (текущая ситуация):*
**{cards[1][0]}**
{random.choice([
    "Текущая ситуация требует вашего внимания и осознанности.",
    "Карта указывает на ключевые энергии, действующие в вашей жизни сейчас."
])}

*Будущее (возможное развитие):*
**{cards[2][0]}**
{random.choice([
    "Будущее развитие зависит от ваших текущих решений.",
    "Карта показывает потенциальный результат ваших действий."
])}"""
    await query.message.reply_text(tarot_text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')

async def handle_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        tariff_map = {
            "premium_1": {"days": 30, "price": 29900},
            "premium_3": {"days": 90, "price": 79900},
            "premium_12": {"days": 365, "price": 199900}
        }
        tariff = tariff_map.get(query.data)
        if not tariff:
            return
        payment_id = str(uuid.uuid4())
        db.save_payment(payment_id, user_id, tariff['days'], tariff['price']/100)
        payload = f"{user_id}_{tariff['days']}_{payment_id}"
        prices = [LabeledPrice(label=f"Премиум на {tariff['days']} дней", amount=tariff['price'])]
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=f"💎 Премиум подписка на {tariff['days']} дней",
            description=f"Полный доступ ко всем функциям бота на {tariff['days']} дней",
            payload=payload,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter="premium_subscription",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            disable_notification=False,
            protect_content=False
        )
        logger.info(f"💳 Инвойс отправлен: пользователь {user_id}, тариф {tariff['days']} дней")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки инвойса: {e}")
        await query.message.reply_text("❌ Ошибка создания счета на оплату. Попробуйте позже.", reply_markup=get_main_keyboard(user_id))

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)
    logger.info(f"✅ Pre-checkout подтвержден: {query.id}")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    try:
        if payment.invoice_payload:
            payload_parts = payment.invoice_payload.split('_')
            if len(payload_parts) >= 3:
                payment_id = payload_parts[2]
                tariff_days = int(payload_parts[1])
                db.update_payment_status(payment_id, 'succeeded')
                premium_until = db.add_premium(user_id, tariff_days)
                success_text = f"""💎 *ПОЗДРАВЛЯЕМ! ПРЕМИУМ АКТИВИРОВАН!* 🎉

✅ *Оплата прошла успешно!*
💰 *Сумма:* {payment.total_amount / 100}₽
📅 *Тариф:* {tariff_days} дней
📅 *Премиум активен до:* {premium_until.split()[0]}

Теперь тебе доступны ВСЕ функции бота! ✨"""
                await update.message.reply_text(success_text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
                logger.info(f"✅ Премиум активирован: пользователь {user_id}, {tariff_days} дней")
                return
        await update.message.reply_text("✅ Оплата прошла успешно! Премиум активирован.", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"❌ Ошибка обработки платежа: {e}")
        await update.message.reply_text("✅ Оплата прошла успешно! Если премиум не активировался, обратитесь в поддержку.", reply_markup=get_main_keyboard(user_id))

async def handle_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        await query.edit_message_text("🔙 Возвращаемся в главное меню...", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")
        try:
            await query.message.reply_text("🔙 Возвращаемся в главное меню:", reply_markup=get_main_keyboard(user_id))
        except Exception as e2:
            logger.error(f"❌ Ошибка возврата: {e2}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if error:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {error}", exc_info=error)
        try:
            if update and update.effective_user:
                error_text = "😔 *Произошла ошибка*\n\nПопробуйте еще раз или вернитесь в главное меню."
                await context.bot.send_message(chat_id=update.effective_user.id, text=error_text, parse_mode='Markdown', reply_markup=get_main_keyboard(update.effective_user.id))
        except Exception as send_error:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {send_error}")

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
        
        app.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА ЗАПУСКА: {e}")
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")

if __name__ == "__main__":
    main()
