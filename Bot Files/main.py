import asyncio
import os
import logging
import json
import shutil
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import LabeledPrice, ContentType
from aiogram.utils.executor import start_polling
from aiogram.utils.exceptions import Unauthorized, BotKicked
from aiogram.utils import executor
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram_proxy import normalize_telegram_proxy
from aiogram.utils.exceptions import TelegramAPIError
from functools import wraps
import asyncpg
import subprocess
import signal
import shlex

# Функция /start 
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log_info.txt"),
        logging.StreamHandler()
    ]
)

API_TOKEN = os.getenv('BOT_API_TOKEN')
TELEGRAM_PROXY = normalize_telegram_proxy(os.getenv('TELEGRAM_PROXY'))
PAY_TOKEN = os.getenv('PAY_TOKEN')
GROUP_ID = os.getenv('GROUP_ID')
CHANNEL_ID = os.getenv('CHANNEL_ID')
PRICE_AMOUNT = int(os.getenv('PRICE', '10000'))  # 10000 копеек = 100 рублей

DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT', '5432')

if not API_TOKEN or not PAY_TOKEN or not DB_USER or not DB_PASSWORD or not DB_NAME or not DB_HOST:
    raise ValueError("Не все переменные окружения загружены корректно")

# Создание экземпляра бота и диспетчера (TELEGRAM_PROXY — локальное тестирование через SOCKS/HTTP)
bot = Bot(token=API_TOKEN, proxy=TELEGRAM_PROXY)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)



# Подключение к базе данных
async def create_db_pool():
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )

db_pool = None

BASE_DIR = '/root/domastroi/user_bots/'
SOURCE_SCRIPT = '/root/domastroi/test.py'





#---------------------------------------------------------#

# subprocess.run(['python', 'test.py'])

# async def start_user_bot(message: types.Message):
#     try:
#         # Путь к скрипту оболочки
#         script_path = '/Users/wschudo/domastroi_admin_bot/start_user_bot.sh'
        
#         # Создание скрипта оболочки
#         with open(script_path, 'w') as file:
#             file.write(f'''#!/bin/bash
# source /Users/wschudo/domastroi_admin_bot/venv/bin/activate
# python /Users/wschudo/domastroi_admin_bot/test.py
# ''')
        
#         # Сделать скрипт исполняемым
#         os.chmod(script_path, 0o755)
        
#         # Запуск скрипта в новом процессе
#         process = subprocess.Popen(script_path, shell=True, executable='/bin/bash')
        
#         # Отправка сообщения пользователю об успешном запуске
#         await message.answer("Пользовательский бот успешно запущен!")
#     except Exception as e:
#         # Обработка ошибок
#         await message.answer(f"Произошла ошибка при запуске бота: {e}")

# @dp.message_handler(commands='start_bot')

# async def handle_start_bot(message: types.Message):
#     await start_user_bot(message)

#---------------------------------------------------------#

# Определение состояний FSM
class Form(StatesGroup):
    api_key = State()
    group_username = State()
    channel_username = State()
    group_id = State()
    channel_id = State()
    add_admin_id = State()
    add_admin_login = State()
    broadcast_text = State()
    broadcast_image = State()
    confirm_broadcast = State()
    user_page = State()
    user_detail = State()
    add_admin_id = State()
    add_admin_login = State()

class SetupForm(StatesGroup):
    page = State()  # Для отслеживания текущей страницы

class HelpForm(StatesGroup):
    page = State()  # Для отслеживания текущей страницы


# Создание клавиатуры
async def get_main_keyboard(user_id):
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            SELECT pay, date_stop FROM users WHERE id_telegram = $1
            """,
            user_id
        )
    if result and result['pay'] == 1:
        subscription_text = "⭐️ Моя подписка"
        remaining_days = (result['date_stop'] - datetime.now()).days
        buy_text = f"Осталось {remaining_days} дней"
    else:
        subscription_text = "🔒 Моя подписка"
        buy_text = "Оформить подписку"

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        ["О нас", buy_text],
        [subscription_text, "Контакты"],
        ["Хелп", "Настройка"]
    ]
    for row in buttons:
        keyboard.add(*row)
    return keyboard

# Проверка статуса пользователя (BAN)

def check_status(handler):
    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        async with db_pool.acquire() as connection:
            user = await connection.fetchrow(
                """
                SELECT status FROM users WHERE id_telegram = $1
                """,
                message.from_user.id
            )
            if user and user['status'] == 1:
                await message.answer("Вы нарушили правила и\nбыли заблокированы ❌")
                return
        await handler(message, *args, **kwargs)
    return wrapper

# Создание клавиатуры для подписки
def get_subscription_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        ["Время окончания подписки", "Продлить подписку"],
        ["Установить API KEY", "Изменить API KEY"],
        ["Запуск 🤖"],
        ["Назад"]
    ]
    for row in buttons:
        keyboard.add(*row)
    return keyboard


# Команда /start
@dp.message_handler(commands='start')
@check_status
async def cmd_start(message: types.Message):
    keyboard = await get_main_keyboard(message.from_user.id)
    async with db_pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO users (id_telegram, tg_login, tg_firstname, tg_lastname, registration_time, status, check_update, old_bot_api)
            VALUES ($1, $2, $3, $4, NOW(), 0, 0, NULL)
            ON CONFLICT (id_telegram) DO NOTHING
            """,
            message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name
        )
    await message.answer("Добро пожаловать! Выберите опцию:", reply_markup=keyboard)


# Функция проверки подписки на группу

async def get_group_id():
    async with db_pool.acquire() as connection:
        group_id = await connection.fetchval(
            "SELECT value FROM settings WHERE name = 'group_id'"
        )
    return group_id

async def get_channel_id():
    async with db_pool.acquire() as connection:
        channel_id = await connection.fetchval(
            "SELECT value FROM settings WHERE name = 'channel_id'"
        )
    return channel_id

async def is_user_in_group(user_id):
    try:
        group_id = await get_group_id()
        if not group_id:
            logging.info("GROUP_ID не задан. Пропуск проверки группы.")
            return True
        member = await bot.get_chat_member(group_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except BotKicked:
        logging.error(f"Бот был удален из группы {group_id}")
        return False
    except Exception as e:
        logging.error(e)
        return False

async def is_user_in_channel(user_id):
    try:
        channel_id = await get_channel_id()
        if not channel_id:
            logging.info("CHANNEL_ID не задан. Пропуск проверки канала.")
            return True
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except BotKicked:
        logging.error(f"Бот был удален из канала {channel_id}")
        return False
    except Exception as e:
        logging.error(e)
        return False

@dp.message_handler(lambda message: message.text == "Оформить подписку")
@check_status
async def handle_buy(message: types.Message):
    buy_function_enabled = await get_setting('buy_function_enabled')
    group_username = await get_setting('group_username')
    channel_username = await get_setting('channel_username')

    if buy_function_enabled == 'true':
        user_id = message.from_user.id
        in_group = await is_user_in_group(user_id)
        in_channel = await is_user_in_channel(user_id)
        if in_group and in_channel:
            # Продолжить с процессом оплаты
            await buy_subscription(message)
        else:
            # Уведомить пользователя о необходимости подписаться на группу и/или канал
            msg = "Для оформления подписки необходимо подписаться на:\n"
            if not in_group:
                msg += f"- Группу {group_username}\n"
            if not in_channel:
                msg += f"- Канал {channel_username}\n"
            await message.answer(msg)
    else:
        await buy_subscription(message)


async def get_setting(name):
    async with db_pool.acquire() as connection:
        result = await connection.fetchval(
            """
            SELECT value FROM settings WHERE name = $1
            """,
            name
        )
    return result

async def update_setting(name, value):
    async with db_pool.acquire() as connection:
        await connection.execute(
            """
            UPDATE settings SET value = $2 WHERE name = $1
            """,
            name, value
        )

# Обработчики нажатий на кнопки меню

# О нас и инлайн клавиатура с услугами
@dp.message_handler(lambda message: message.text == "О нас")
async def about(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Наши продукты", callback_data="services"))
    keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close_message"))
    await message.answer("Мы команда, которая занимается...", reply_markup=keyboard)

# Функция для создания клавиатуры с услугами
def get_services_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("DESIGNER ASSISTANT", callback_data="service_1"))
    # keyboard.add(types.InlineKeyboardButton("Тест", callback_data="service_2"))
    keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close_message"))
    return keyboard

# Функция для создания клавиатуры с кнопками "Назад" и "Закрыть"
def get_service_details_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Назад", callback_data="back_to_services"))
    # keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close_service_details"))
    return keyboard

# Обработчик для инлайн-кнопок "Услуги"
@dp.callback_query_handler(lambda c: c.data == "services")
async def services_callback(callback_query: types.CallbackQuery):
    await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, 
                                text="Узнайте больше про бота для заполнения технического задания на разработку дизайн-проекта жилого помещения:", reply_markup=get_services_keyboard())

# Обработчик для инлайн-кнопок с услугами
@dp.callback_query_handler(lambda c: c.data in ["service_1", "service_2"])
async def service_details_callback(callback_query: types.CallbackQuery):
    if callback_query.data == "service_1":
        text = "Подробности услуги 'Бот для заполнения технического задания на разработку дизайн-проекта жилого помещения'\n\n[Видео](https://example.com/video.mp4)"
    # elif callback_query.data == "service_2":
    #     text = "Подробности услуги 'Тест'\n\n[Видео](https://example.com/video.mp4)"
    await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id,
                                text=text, reply_markup=get_service_details_keyboard(), parse_mode=types.ParseMode.MARKDOWN)

# Обработчик для инлайн-кнопки "Закрыть" и "Назад" в деталях услуги
@dp.callback_query_handler(lambda c: c.data in ["close_service_details", "back_to_services"])
async def close_or_back_services_callback(callback_query: types.CallbackQuery):
    if callback_query.data == "close_service_details":
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    elif callback_query.data == "back_to_services":
        await bot.edit_message_text(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, 
                                    text="Узнайте больше про бота для заполнения технического задания на разработку дизайн-проекта жилого помещения:", reply_markup=get_services_keyboard())

# Обработчик для инлайн-кнопки "Закрыть" в меню "О нас"
@dp.callback_query_handler(lambda c: c.data == "close_message")
async def close_message_callback(callback_query: types.CallbackQuery):
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)



@dp.message_handler(lambda message: message.text == "Оформить подписку")
async def buy_subscription(message: types.Message):
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            "SELECT pay, date_stop FROM users WHERE id_telegram = $1",
            message.from_user.id
        )
        if result and result['pay'] == 1:
            date_stop = result['date_stop'].strftime("%d.%m.%Y %H:%M")
            await message.answer(f"Вы уже подписаны. Ваша подписка активна до: {date_stop}")
        else:
            PRICE = LabeledPrice(label="Подписка на 1 месяц", amount=PRICE_AMOUNT)
            await bot.send_invoice(
                message.chat.id,
                title="Активация бота на 1 месяц",
                description="Активация подписки на бота на 1 месяц",
                provider_token=PAY_TOKEN,
                currency='RUB',
                prices=[PRICE],
                payload="test-invoice-payload",
                need_email=True,
                send_email_to_provider=True,
                provider_data=json.dumps({
                    "receipt": {
                        "customer": {
                            "email": "example@example.com"
                        },
                        "items": [
                            {
                                "description": "Подписка на 1 месяц",
                                "quantity": 1,
                                "amount": {
                                    "value": PRICE_AMOUNT / 100,
                                    "currency": "RUB"
                                },
                                "vat_code": 1,
                                "payment_mode": "full_prepayment",
                                "payment_subject": "service"
                            }
                        ],
                        "tax_system_code": 1
                    }
                })
            )



@dp.message_handler(lambda message: "Моя подписка" in message.text)
@check_status
async def my_subscription(message: types.Message):
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            SELECT pay FROM users WHERE id_telegram = $1
            """,
            message.from_user.id
        )
    if result and result['pay'] == 1:
        await message.answer("Выберите опцию:", reply_markup=get_subscription_keyboard())
    else:
        await message.answer("Подписка не активна.\nПожалуйста, оформите подписку 🫶")



@dp.message_handler(lambda message: message.text == "Контакты")
async def contacts(message: types.Message):
    await message.answer("Наши контакты...")

# Start Модель Хелпер

@dp.message_handler(lambda message: message.text == "Хелп")
async def help_start(message: types.Message, state: FSMContext):
    await state.update_data(page=1)
    await show_help_page(message, 1)

async def show_help_page(message: types.Message, page: int, edit: bool = False):
    if page == 1:
        text = "Первая страница помощи. Здесь находится общий обзор."
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Далее", callback_data="help_next"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="help_close"))
    elif page == 2:
        text = "Вторая страница помощи. Здесь находятся инструкции по использованию."
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Далее", callback_data="help_next"))
        keyboard.add(types.InlineKeyboardButton("Назад", callback_data="help_prev"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="help_close"))
    elif page == 3:
        text = "Третья страница помощи. Здесь находятся часто задаваемые вопросы."
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Назад", callback_data="help_prev"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="help_close"))

    if edit:
        await message.edit_text(text, reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)

@dp.callback_query_handler(lambda c: c.data in ['help_next', 'help_prev', 'help_close'])
async def handle_help_callback(call: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_page = user_data.get('page', 1)
    
    if call.data == 'help_next':
        next_page = current_page + 1
        await state.update_data(page=next_page)
        await show_help_page(call.message, next_page, edit=True)
    elif call.data == 'help_prev':
        prev_page = current_page - 1
        await state.update_data(page=prev_page)
        await show_help_page(call.message, prev_page, edit=True)
    elif call.data == 'help_close':
        await call.message.delete()
        await state.finish()
    await call.answer()


# End Модель Хелпер

# Start Модель Настройка

@dp.message_handler(lambda message: message.text == "Настройка")
async def setup_start(message: types.Message, state: FSMContext):
    await state.update_data(page=1)
    await show_page(message, 1)

async def show_page(message: types.Message, page: int, edit: bool = False):
    if page == 1:
        text = (
        "Подключение своего бота:\n\n"
        "Для подключения необходимо получить API KEY вашего будущего бота.\n"
        "Шаги для получения API ключа:\n\n"
        "1. Откройте Telegram и перейдите в бота @BotFather.\n"
        "2. Нажмите кнопку «/start» или введите эту команду, чтобы начать взаимодействие с @BotFather.\n"
        "3. Введите команду «/newbot», чтобы создать нового бота.\n"
        "4. @BotFather попросит вас указать имя для вашего бота. Например: `Мой первый бот`.\n"
        "5. Затем вас попросят указать уникальное имя пользователя бота (username), которое должно оканчиваться на **bot**.\n"
        "   Например: `MyNewBot_bot` или `MyAwesomeBot_bot`.\n"
        "6. Выбранное уникальное имя пользователя бота (username) будет логином вашего бота для всех пользователей.\n"
        "7. После успешного создания бота, @BotFather отправит вам сообщение с API ключом. Этот ключ выглядит примерно так: \n"
        "   `123456789:ABCdefGhIjKLmNoPQRstUVwXyZ`\n\n"
        "Важно! Никому не передавайте этот ключ, так как он предоставляет полный доступ к вашему боту.\n"
    )
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Далее", callback_data="next"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))
    elif page == 2:
        text = (
        "Теперь у вас есть API ключ. Используйте этот ключ для активации вашего бота в нашем сервисе.\n\n"
        "1. Скопируйте API ключ, который вы получили от @BotFather. Он выглядит примерно так:\n"
        "   `123456789:ABCdefGhIjKLmNoPQRstUVwXyZ`\n\n"
        "2. Перейдите в наше приложение или интерфейс, где нужно подключить бота.\n"
        "3. Войдите раздел «Моя подписка».\n"
        "4. Вставьте скопированный API ключ в «Установить API KEY».\n\n"
        
        "После получения сообщения «Ваш API KEY сохранен ✅» бот будет готов к работе и подключён к нашему сервису.\nВы сможете управлять им через нашу систему.\n\n"
        
        "Запуск бота:\n"
        "1. Для запуска бота перейдите в меню подписки и нажмите кнопку «Запуск 🤖»\n"
        "2. Нажмите кнопку «Запустить бота». Вы получите сообщение о том, что бот успешно запущен!\nТеперь ваш бот будет доступен для всех пользователей. Вы сможете проверять его статус, запускать и останавливать его через наш интерфейс.\n"
        
        "Важное замечание:\n"
        "Если бот не запускается, убедитесь, что API ключ введён правильно. Также проверьте, что ваш бот не заблокирован или не удалён в Telegram."
        "Если вы сделаете нового бота, то ваш API KEY изменится. Вам необходимо скопировать новый API KEY бота и нажать на кнопку «Изменить API KEY»"
    )

        # Добавьте URL изображения ниже
        # text += "\n[Изображение](https://ichudo.pro/othet_files/example.jpg)"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Далее", callback_data="next"))
        keyboard.add(types.InlineKeyboardButton("Назад", callback_data="prev"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))
    elif page == 3:
        text = (
            "Декорирование бота:\n\n"
            "Теперь давайте настроим внешний вид и поведение вашего бота.\n\n"
            "1. **Установка изображения профиля бота**:\n"
            "   - Откройте диалог с ботом @BotFather и введите команду `/setuserpic`.\n"
            "   - Выберите вашего бота и загрузите изображение профиля. Это изображение будет отображаться в Telegram как аватар вашего бота.\n\n"
            "2. **Приветственное сообщение**:\n"
            "   - Приветственное сообщение — это первое, что видит пользователь после команды `/start`.\n"
            "   - Пример: «Любой качественный дизайн-проект начинается с пожеланий Заказчика. Мы подготовили данную анкету для того, чтобы узнать ваши пожелания и предпочтения к будущему интерьеру и ускорить разработку дизайн-проекта. Пожалуйста, заполните эту анкету максимально подробно..\n\n"
            "3. **Настройка команд в меню**:\n"
            "   - Для удобства можно добавить команды в меню через @BotFather.\n"
            "   - Введите команду `/setcommands` и добавьте следующие команды:\n\n"
            "     - `/start` — Запуск\n"
            "     - `/menu` — Меню\n"
            "     - `/go` — Начать\n"
            "     - `/help` — Хелпер\n\n"
            "4. **Установка описания и контактов**:\n"
            "   - Введите команду `/setdescription` в @BotFather, чтобы добавить описание вашего бота.\n"
            "   - Пример: Наши  контакты: +7 (000) 000-00-00»."
        )
        # Добавьте URL видео ниже
        # text += "\n[Видео](https://ichudo.pro/othet_files/coming_soon.mov)"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Назад", callback_data="prev"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))

    if edit:
        await message.edit_text(text, reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)

@dp.callback_query_handler(lambda c: c.data in ['next', 'prev', 'close'])
async def handle_callback(call: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_page = user_data.get('page', 1)
    
    if call.data == 'next':
        next_page = current_page + 1
        await state.update_data(page=next_page)
        await show_page(call.message, next_page, edit=True)
    elif call.data == 'prev':
        prev_page = current_page - 1
        await state.update_data(page=prev_page)
        await show_page(call.message, prev_page, edit=True)
    elif call.data == 'close':
        await call.message.delete()
        await state.finish()
    await call.answer()


# End Модель Настройка



@dp.message_handler(lambda message: message.text == "Время окончания подписки")
async def subscription_end_time(message: types.Message):
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            SELECT pay, date_stop FROM users WHERE id_telegram = $1
            """,
            message.from_user.id
        )
        if result and result['pay'] == 1:
            date_stop = result['date_stop'].strftime("%d.%m.%Y %H:%M")
            await message.answer(f"Ваша подписка активна до: {date_stop}")
        else:
            await message.answer("Вы не являетесь подписчиком 🤔")



@dp.message_handler(lambda message: message.text == "Продлить подписку")
async def renew_subscription(message: types.Message):
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            "SELECT pay, date_stop FROM users WHERE id_telegram = $1",
            message.from_user.id
        )
        if result and result['pay'] == 1:
            PRICE = LabeledPrice(label="Подписка на 1 месяц", amount=PRICE_AMOUNT)
            await bot.send_invoice(
                message.chat.id,
                title="Продление подписки",
                description="Продление подписки на бота на 1 месяц",
                provider_token=PAY_TOKEN,
                currency='RUB',
                prices=[PRICE],
                payload="renew-invoice-payload",
                need_email=True,
                send_email_to_provider=True,
                provider_data=json.dumps({
                    "receipt": {
                        "customer": {
                            "email": "example@example.com"
                        },
                        "items": [
                            {
                                "description": "Продление подписки на 1 месяц",
                                "quantity": 1,
                                "amount": {
                                    "value": PRICE_AMOUNT / 100,
                                    "currency": "RUB"
                                },
                                "vat_code": 1,
                                "payment_mode": "full_prepayment",
                                "payment_subject": "service"
                            }
                        ],
                        "tax_system_code": 1
                    }
                })
            )
        else:
            await message.answer("Подписка не активна. Пожалуйста, оформите подписку 🫶")



@dp.message_handler(lambda message: message.text == "Установить API KEY")
async def insert_api_key(message: types.Message):
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            SELECT pay, bot_api FROM users WHERE id_telegram = $1
            """,
            message.from_user.id
        )
        if result and result['pay'] == 1:
            if result['bot_api']:
                await message.answer("API KEY уже установлен 🔐 Если вы хотите его изменить, выберите «Изменить API KEY»")
            else:
                await Form.api_key.set()
                await message.answer("Пожалуйста, введите ваш API KEY 🔑")
        else:
            await message.answer("Подписка не активна. Пожалуйста, оформите подписку 🫶")

@dp.message_handler(lambda message: message.text == "Изменить API KEY")
async def change_api_key(message: types.Message):
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            SELECT pay, bot_api FROM users WHERE id_telegram = $1
            """,
            message.from_user.id
        )
        if result and result['pay'] == 1:
            if result['bot_api']:
                await Form.api_key.set()
                await message.answer("Пожалуйста, введите ваш новый API KEY 🔑")
            else:
                await message.answer("API KEY не заполнен ⛔️ Пожалуйста, сначала установите API KEY 🔑")
        else:
            await message.answer("Подписка не активна. Пожалуйста, оформите подписку 🫶")


@dp.message_handler(lambda message: message.text == "Назад")
async def go_back(message: types.Message):
    keyboard = await get_main_keyboard(message.from_user.id)
    await message.answer("Выберите опцию:", reply_markup=keyboard)



@dp.message_handler(state=Form.api_key)
async def process_api_key(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['api_key'] = message.text
    async with db_pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            SELECT bot_api FROM users WHERE id_telegram = $1
            """,
            message.from_user.id
        )
        if result and result['bot_api']:
            await connection.execute(
                """
                UPDATE users SET old_bot_api = bot_api, bot_api = $1 WHERE id_telegram = $2
                """,
                data['api_key'], message.from_user.id
            )
        else:
            await connection.execute(
                """
                UPDATE users SET bot_api = $1 WHERE id_telegram = $2
                """,
                data['api_key'], message.from_user.id
            )
    await state.finish()
    await message.answer("Ваш API KEY сохранен ✅", reply_markup=await get_main_keyboard(message.from_user.id))


# Обработчики платежей
@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    transaction_type = None
    async with db_pool.acquire() as connection:
        if payload == 'renew-invoice-payload':
            result = await connection.fetchrow(
                """
                SELECT date_stop FROM users WHERE id_telegram = $1
                """,
                message.from_user.id
            )
            if result:
                new_date_stop = result['date_stop'] + timedelta(days=31)
                await connection.execute(
                    """
                    UPDATE users SET date_stop = $1, check_update = 0 WHERE id_telegram = $2
                    """,
                    new_date_stop, message.from_user.id
                )
                await message.answer(f"Подписка успешно продлена до {new_date_stop.strftime('%d.%m.%Y %H:%M')} 😎")
                transaction_type = "Продление"
                renewal_message = True
        else:
            end_date = datetime.now() + timedelta(days=31)
            await connection.execute(
                """
                UPDATE users SET pay = 1, date_pay = $1, date_stop = $2,
                telegram_payment_charge_id = $3, provider_payment_charge_id = $4, check_update = 0
                WHERE id_telegram = $5
                """,
                datetime.now(), end_date,
                message.successful_payment.telegram_payment_charge_id,
                message.successful_payment.provider_payment_charge_id,
                message.from_user.id
            )
            await message.answer(f"Спасибо за покупку! Ваша подписка активна до {end_date.strftime('%d.%m.%Y %H:%M')} 😎", reply_markup=await get_main_keyboard(message.from_user.id))
            transaction_type = "Покупка"
            renewal_message = False

        # Запись данных об оплате в таблицу payments
        payment_time = datetime.now()
        await connection.execute(
            """
            INSERT INTO payments (tg_login, payment_time, telegram_payment_charge_id, provider_payment_charge_id, transaction_type)
            VALUES ($1, $2, $3, $4, $5)
            """,
            message.from_user.username, payment_time,
            message.successful_payment.telegram_payment_charge_id,
            message.successful_payment.provider_payment_charge_id,
            transaction_type
        )

        # Получение ID транзакции
        transaction_id = await connection.fetchval(
            """
            SELECT id FROM payments WHERE telegram_payment_charge_id = $1
            """,
            message.successful_payment.telegram_payment_charge_id
        )
        
        # Отправка уведомлений администраторам
        # Получение списка администраторов из базы данных

        admin_ids = await connection.fetch(
            """
            SELECT id_telegram FROM admin_list
            """
        )

        for admin in admin_ids:
            await bot.send_message(
                admin['id_telegram'],
                f"Новая транзакция:\n\n"
                f"ID транзакции: {transaction_id}\n"
                f"ID пользователя: {message.from_user.id}\n"
                f"Логин: {message.from_user.username}\n"
                f"Имя: {message.from_user.first_name}\n"
                f"Фамилия: {message.from_user.last_name}\n"
                f"Время оформления: {payment_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"Тип транзакции: {transaction_type}"
            )

    keyboard = await get_main_keyboard(message.from_user.id)
    if renewal_message:
        await message.answer("Ваша подписка продлена, наслаждайтесь дополнительным месяцем 😉", reply_markup=await get_main_keyboard(message.from_user.id))
    else:
        await message.answer("Вы разблокировали все функции 🤩", reply_markup=await get_main_keyboard(message.from_user.id))

    





# Команда /payd для моделирования успешной оплаты
# @dp.message_handler(commands='payd')
# async def cmd_payd(message: types.Message):
#     end_date = datetime.now() + timedelta(days=30)
#     async with db_pool.acquire() as connection:
#         await connection.execute(
#             """
#             UPDATE users SET pay = 1, date_pay = $1, date_stop = $2,
#             telegram_payment_charge_id = $3, provider_payment_charge_id = $4
#             WHERE id_telegram = $5
#             """,
#             datetime.now(), end_date,
#             "test_telegram_payment_charge_id", "test_provider_payment_charge_id",
#             message.from_user.id
#         )
#     text = f"Моделирование успешной оплаты завершено. Ваша подписка активна до {end_date.strftime('%d.%m.%Y %H:%M')}."
#     keyboard = await get_main_keyboard(message.from_user.id)
#     await message.answer(text, reply_markup=keyboard)


# @dp.message_handler(commands='payd_renew')
# async def cmd_payd_renew(message: types.Message):
#     async with db_pool.acquire() as connection:
#         result = await connection.fetchrow(
#             """
#             SELECT date_stop FROM users WHERE id_telegram = $1
#             """,
#             message.from_user.id
#         )
#         if result and result['date_stop']:
#             new_date_stop = result['date_stop'] + timedelta(days=30)
#             await connection.execute(
#                 """
#                 UPDATE users SET date_stop = $1 WHERE id_telegram = $2
#                 """,
#                 new_date_stop, message.from_user.id
#             )
#             await message.answer(f"Моделирование успешного продления подписки завершено. Ваша подписка активна до {new_date_stop.strftime('%d.%m.%Y %H:%M')}.")
#         else:
#             await message.answer("Подписка не активна. Пожалуйста, оформите подписку.")


# Асинхронная задача для проверки окончания подписки
async def check_subscriptions():
    while True:
        async with db_pool.acquire() as connection:
            now = datetime.now()
            five_days_before = now + timedelta(days=5)

            # Проверка пользователей, которым нужно отправить уведомление за 5 дней до окончания подписки
            users_to_notify = await connection.fetch(
                """
                SELECT id_telegram, date_stop FROM users WHERE pay = 1 AND date_stop BETWEEN $1 AND $2 AND check_update = 0
                """,
                now, five_days_before
            )
            for user in users_to_notify:
                message = f"⚠️ Ваша подписка скоро закончится 😮\nОсталось 5 дней\n{user['date_stop'].strftime('%d.%m.%Y %H:%M')} 🥺"
                keyboard = await get_main_keyboard(user['id_telegram'])
                await bot.send_message(user['id_telegram'], message, reply_markup=keyboard)
                logging.info(f"Уведомление отправлено пользователю {user['id_telegram']}: {message}")
                await connection.execute(
                    """
                    UPDATE users SET check_update = 1 WHERE id_telegram = $1
                    """,
                    user['id_telegram']
                )

            # Проверка пользователей, чья подписка закончилась
            users_to_expire = await connection.fetch(
                """
                SELECT id_telegram FROM users WHERE pay = 1 AND date_stop <= $1
                """,
                now
            )
            for user in users_to_expire:
                await connection.execute(
                    """
                    UPDATE users SET pay = 0, date_pay = NULL, date_stop = NULL,
                    telegram_payment_charge_id = NULL, provider_payment_charge_id = NULL, check_update = 0
                    WHERE id_telegram = $1
                    """,
                    user['id_telegram']
                )
                message = "🚫 Ваша подписка закончилась 😔"
                keyboard = await get_main_keyboard(user['id_telegram'])
                await bot.send_message(user['id_telegram'], message, reply_markup=keyboard)
                logging.info(f"Уведомление отправлено пользователю {user['id_telegram']}: {message}")

        logging.info("Проверка подписок завершена.")
        await asyncio.sleep(3600)  # Проверка каждые 60 секунд






# Функции админа /admin

def admin_only(handler):
    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        async with db_pool.acquire() as connection:
            admin = await connection.fetchrow(
                """
                SELECT id_telegram FROM admin_list WHERE id_telegram = $1
                """,
                message.from_user.id
            )
            if not admin:
                await message.answer("У вас нет прав для выполнения этой команды 🤨")
                return
        await handler(message, *args, **kwargs)
    return wrapper

async def get_admin_keyboard(user_id):
    async with db_pool.acquire() as connection:
        super_admin = await connection.fetchval(
            """
            SELECT super_admin FROM admin_list WHERE id_telegram = $1
            """,
            user_id
        )
        buy_function_enabled = await get_setting('buy_function_enabled')
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        
        if buy_function_enabled == 'true':
            buttons = [["Выключить подписку 🚫"]]
        else:
            buttons = [["Включить подписку ✅"]]
        
        buttons.append(["Настройки подписки", "Пользователи"])

        if super_admin == 1:
            buttons.append(["Добавить администратора", "Удалить администратора"])
            buttons.append(["Рассылка", "Who Online?"])
        
        buttons.append(["Назад"])
        
        for row in buttons:
            keyboard.add(*row)
    return keyboard

def get_return_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Вернуться в админ-панель"))
    return keyboard

async def get_subscription_settings_keyboard():
    group_username = await get_setting('group_username')
    channel_username = await get_setting('channel_username')
    group_id = await get_setting('group_id')
    channel_id = await get_setting('channel_id')

    group_status = "✅" if group_username and group_id else "⚠️"
    channel_status = "✅" if channel_username and channel_id else "⚠️"

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        [f"Группа для подписки {group_status}", f"Канал для подписки {channel_status}"],
        [f"ID группы для подписки {group_status}", f"ID канала для подписки {channel_status}"],
        ["Очистить данные группы", "Очистить данные канала"],
        ["Вернуться"]
    ]
    for row in buttons:
        keyboard.add(*row)
    return keyboard



@dp.message_handler(commands='admin')
@admin_only
async def admin_menu(message: types.Message):
    keyboard = await get_admin_keyboard(message.from_user.id)
    await message.answer("Меню администратора:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Настройки подписки")
async def subscription_settings_menu(message: types.Message):
    keyboard = await get_subscription_settings_keyboard()
    await message.answer("Настройки подписки:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Вернуться")
async def handle_back(message: types.Message):
    user_id = message.from_user.id
    keyboard = await get_admin_keyboard(user_id)
    await message.answer("Меню администратора:", reply_markup=keyboard)

# Функции включения/выключения функции подписки на группу

@dp.message_handler(lambda message: message.text == "Включить подписку ✅")
@admin_only
async def enable_subscription(message: types.Message):
    await update_setting('buy_function_enabled', 'true')
    await message.answer("Функция подписки включена ✅", reply_markup=await get_admin_keyboard(message.from_user.id))

@dp.message_handler(lambda message: message.text == "Выключить подписку 🚫")
@admin_only
async def disable_subscription(message: types.Message):
    await update_setting('buy_function_enabled', 'false')
    await message.answer("Функция подписки выключена 🚫", reply_markup=await get_admin_keyboard(message.from_user.id))

@dp.message_handler(lambda message: "Группа для подписки" in message.text)
@admin_only
async def handle_group_subscription(message: types.Message):
    await message.answer("Пожалуйста, введите логин группы в формате @username:")
    await Form.group_username.set()

@dp.message_handler(state=Form.group_username)
@admin_only
async def process_group_username(message: types.Message, state: FSMContext):
    group_username = message.text
    if group_username.startswith("@"):
        await update_setting('group_username', group_username)
        await state.finish()
        await message.answer(f"Логин группы для подписки сохранен: {group_username}", reply_markup=await get_subscription_settings_keyboard())
    else:
        await message.answer("Некорректный формат. Пожалуйста, введите логин группы в формате @username:")

        
@dp.message_handler(lambda message: "Канал для подписки" in message.text)
@admin_only
async def set_group_subscription(message: types.Message):
    await message.answer("Пожалуйста, введите логин канала в формате @username:")
    await Form.channel_username.set()

@dp.message_handler(state=Form.channel_username)
@admin_only
async def process_channel_username(message: types.Message, state: FSMContext):
    channel_username = message.text
    if channel_username.startswith("@"):
        await update_setting('channel_username', channel_username)
        await state.finish()
        await message.answer(f"Логин канала для подписки сохранен: {channel_username}", reply_markup=await get_subscription_settings_keyboard())
    else:
        await message.answer("Некорректный формат. Пожалуйста, введите логин канала в формате @username:")

# Функция заполнения ID груп для подписки

@dp.message_handler(lambda message: "ID группы для подписки" in message.text)
@admin_only
async def set_id_subscription(message: types.Message):
    await message.answer("Пожалуйста, введите ID группы в формате -XXXXXXXXXXXXX:")
    await Form.group_id.set()

@dp.message_handler(state=Form.group_id)
@admin_only
async def process_group_id(message: types.Message, state: FSMContext):
    group_id = message.text
    if group_id.startswith("-"):
        await update_setting('group_id', group_id)
        await state.finish()
        await message.answer(f"ID группы для подписки сохранен: {group_id}", reply_markup=await get_subscription_settings_keyboard())
    else:
        await message.answer("Некорректный формат. Пожалуйста, введите ID группы в формате -XXXXXXXXXXXXX:")

        
@dp.message_handler(lambda message: "ID канала для подписки" in message.text)
@admin_only
async def set_id_subscription(message: types.Message):
    await message.answer("Пожалуйста, введите ID канала в формате -XXXXXXXXXXXXX:")
    await Form.channel_id.set()

@dp.message_handler(state=Form.channel_id)
@admin_only
async def process_channel_username(message: types.Message, state: FSMContext):
    channel_id = message.text
    if channel_id.startswith("-"):
        await update_setting('channel_id', channel_id)
        await state.finish()
        await message.answer(f"ID канала для подписки сохранен: {channel_id}", reply_markup=await get_subscription_settings_keyboard())
    else:
        await message.answer("Некорректный формат. Пожалуйста, введите ID канала в формате -XXXXXXXXXXXXX:")

# Функции очистки полей для рассылки

@dp.message_handler(lambda message: message.text == "Очистить данные группы")
async def handle_clear_group_data(message: types.Message):
    await update_setting('group_username', '')
    await update_setting('group_id', '')
    await message.answer("Данные группы для подписки успешно очищены ✅", reply_markup=await get_subscription_settings_keyboard())

@dp.message_handler(lambda message: message.text == "Очистить данные канала")
async def handle_clear_channel_data(message: types.Message):
    await update_setting('channel_username', '')
    await update_setting('channel_id', '')
    await message.answer("Данные канала для подписки успешно очищены ✅", reply_markup=await get_subscription_settings_keyboard())

# Функции добавления администраторов

@dp.message_handler(lambda message: message.text == "Добавить администратора")
@admin_only
async def add_admin(message: types.Message):
    user_id = message.from_user.id
    async with db_pool.acquire() as connection:
        super_admin = await connection.fetchval(
            """
            SELECT super_admin FROM admin_list WHERE id_telegram = $1
            """,
            user_id
        )
    if super_admin == 1:
        await message.answer("Пожалуйста, введите ID пользователя:", reply_markup=get_return_keyboard())
        await Form.add_admin_id.set()
    else:
        await message.answer("🖕")

@dp.message_handler(state=Form.add_admin_id)
@admin_only
async def process_add_admin_id(message: types.Message, state: FSMContext):
    if message.text == "Вернуться в админ-панель":
        await state.finish()
        await message.answer("Вы вернулись в админ-панель", reply_markup=await get_admin_keyboard(message.from_user.id))
        return

    try:
        user_id = int(message.text)
        async with state.proxy() as data:
            data['user_id'] = user_id
        await message.answer("Пожалуйста, введите логин пользователя в формате @username:", reply_markup=get_return_keyboard())
        await Form.add_admin_login.set()
    except ValueError:
        await message.answer("Некорректный формат ID. Пожалуйста, введите числовой ID пользователя:")

@dp.message_handler(state=Form.add_admin_login)
@admin_only
async def process_add_admin_login(message: types.Message, state: FSMContext):
    if message.text == "Вернуться в админ-панель":
        await state.finish()
        await message.answer("Вы вернулись в админ-панель", reply_markup=await get_admin_keyboard(message.from_user.id))
        return

    login = message.text
    if login.startswith("@"):
        async with state.proxy() as data:
            user_id = data['user_id']
        async with db_pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO admin_list (id_telegram, tg_login) VALUES ($1, $2)
                ON CONFLICT (id_telegram) DO NOTHING
                """,
                user_id, login
            )
        await state.finish()
        await message.answer(f"Пользователь с ID {user_id} и логином {login} добавлен в администраторы 🙌", reply_markup=await get_admin_keyboard(message.from_user.id))
    else:
        await message.answer("Некорректный формат логина. Пожалуйста, введите логин пользователя в формате @username:", reply_markup=get_return_keyboard())


# Функции удаления администраторов

@dp.message_handler(lambda message: message.text == "Удалить администратора")
@admin_only
async def remove_admin(message: types.Message):
    user_id = message.from_user.id
    async with db_pool.acquire() as connection:
        super_admin = await connection.fetchval(
            """
            SELECT super_admin FROM admin_list WHERE id_telegram = $1
            """,
            user_id
        )
        if super_admin == 1:
            admins = await connection.fetch(
                """
                SELECT id_telegram, tg_login FROM admin_list WHERE super_admin = 0
                """
            )
            keyboard = types.InlineKeyboardMarkup()
            for admin in admins:
                keyboard.add(types.InlineKeyboardButton(f"{admin['id_telegram']} {admin['tg_login']}", callback_data=f"remove_admin_{admin['id_telegram']}"))
            keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))
            await message.answer("Выберите администратора для удаления:", reply_markup=keyboard)
        else:
            await message.answer("🖕")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("remove_admin_"))
@admin_only
async def process_remove_admin(callback_query: types.CallbackQuery):
    admin_id = int(callback_query.data.split("_")[2])
    async with db_pool.acquire() as connection:
        await connection.execute(
            """
            DELETE FROM admin_list WHERE id_telegram = $1
            """,
            admin_id
        )
        # Обновление списка администраторов после удаления
        admins = await connection.fetch(
            """
            SELECT id_telegram, tg_login FROM admin_list WHERE super_admin = 0
            """
        )
        keyboard = types.InlineKeyboardMarkup()
        for admin in admins:
            keyboard.add(types.InlineKeyboardButton(f"{admin['id_telegram']} {admin['tg_login']}", callback_data=f"remove_admin_{admin['id_telegram']}"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))
    await bot.answer_callback_query(callback_query.id, text=f"Администратор с ID {admin_id} удален.")
    await bot.edit_message_text("Выберите администратора для удаления:", chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "close")
async def close_callback(callback_query: types.CallbackQuery):
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    await bot.answer_callback_query(callback_query.id)

# Функция рассылки

@dp.message_handler(lambda message: message.text == "Рассылка")
@admin_only
async def broadcast_start(message: types.Message):
    user_id = message.from_user.id
    async with db_pool.acquire() as connection:
        super_admin = await connection.fetchval(
            """
            SELECT super_admin FROM admin_list WHERE id_telegram = $1
            """,
            user_id
        )
    if super_admin == 1:
        await message.answer("Пожалуйста, введите текст рассылки:")
        await Form.broadcast_text.set()
    else:
        await message.answer("🖕")


@dp.message_handler(state=Form.broadcast_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['broadcast_text'] = message.text
    await message.answer("Теперь отправьте изображение или нажмите 'Нет изображения'", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Нет изображения"))
    await Form.broadcast_image.set()

@dp.message_handler(content_types=['photo'], state=Form.broadcast_image)
async def process_broadcast_image(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['broadcast_image'] = message.photo[-1].file_id
    await show_broadcast_preview(message, state)

@dp.message_handler(lambda message: message.text == "Нет изображения", state=Form.broadcast_image)
async def process_broadcast_no_image(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['broadcast_image'] = None
    await show_broadcast_preview(message, state)

async def show_broadcast_preview(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        text = data['broadcast_text']
        image = data.get('broadcast_image')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отправить", callback_data="confirm_broadcast"))
    markup.add(types.InlineKeyboardButton("Отменить", callback_data="cancel_broadcast"))
    
    if image:
        await message.answer_photo(photo=image, caption=text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
    
    await Form.confirm_broadcast.set()

@dp.callback_query_handler(lambda c: c.data == "confirm_broadcast", state=Form.confirm_broadcast)
async def confirm_broadcast(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()
    await call.message.answer("Рассылка началась. Пожалуйста, подождите...")
    
    async with state.proxy() as data:
        text = data['broadcast_text']
        image = data.get('broadcast_image')
    
    total = 0
    success = 0
    failed = 0
    
    async with db_pool.acquire() as connection:
        users = await connection.fetch("SELECT id_telegram FROM users")
        for user in users:
            try:
                if image:
                    await bot.send_photo(user['id_telegram'], photo=image, caption=text, parse_mode="Markdown")
                else:
                    await bot.send_message(user['id_telegram'], text, parse_mode="Markdown")
                success += 1
            except Exception as e:
                failed += 1
            total += 1
    
    await state.finish()
    await call.message.answer(f"Рассылка завершена.\nВсего отправлено: {total} 📧\nДоставлено: {success} 📩\nНе доставлено: {failed} ✉️", reply_markup=await get_admin_keyboard(call.from_user.id))

@dp.callback_query_handler(lambda c: c.data == "cancel_broadcast", state=Form.confirm_broadcast)
async def cancel_broadcast(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.delete()
    await call.message.answer("Рассылка отменена.", reply_markup=await get_admin_keyboard(call.from_user.id))

# Функция загрузки пользователей

@dp.message_handler(lambda message: message.text == "Пользователи")
@admin_only
async def list_users(message: types.Message, state: FSMContext):
    async with db_pool.acquire() as connection:
        total_users = await connection.fetchval("SELECT COUNT(*) FROM users")
    await state.update_data(total_users=total_users, current_page=0)
    await show_users_page(message, state)

async def show_users_page(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_page = data.get('current_page', 0)
    total_users = data.get('total_users', 0)
    per_page = 10
    offset = current_page * per_page
    
    async with db_pool.acquire() as connection:
        users = await connection.fetch(
            """
            SELECT id, id_telegram, tg_login, status FROM users
            ORDER BY id_telegram
            LIMIT $1 OFFSET $2
            """,
            per_page, offset
        )

    keyboard = types.InlineKeyboardMarkup()
    for user in users:
        status_icon = "✅" if user['status'] == 0 else "⛔️"
        keyboard.add(types.InlineKeyboardButton(f"{status_icon} ID{user['id']} | {user['id_telegram']} {user['tg_login']}", callback_data=f"user_{user['id_telegram']}"))

    if current_page > 0:
        keyboard.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))
    if (current_page + 1) * per_page < total_users:
        keyboard.add(types.InlineKeyboardButton("Вперёд ➡️", callback_data="next_page"))

    keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))
    
    await message.answer(
        f"Всего пользователей: {total_users}\n"
        f"Страница {current_page + 1}/{(total_users + per_page - 1) // per_page}",
        reply_markup=keyboard
    )
    await Form.user_page.set()


@dp.callback_query_handler(lambda c: c.data in ["prev_page", "next_page"], state=Form.user_page)
@admin_only
async def change_page(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_page = data.get('current_page', 0)
    
    if call.data == "prev_page":
        current_page -= 1
    elif call.data == "next_page":
        current_page += 1
    
    await state.update_data(current_page=current_page)
    await call.message.delete()
    await show_users_page(call.message, state)

@dp.callback_query_handler(lambda c: c.data.startswith("user_"), state=Form.user_page)
@admin_only
async def show_user_detail(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    async with db_pool.acquire() as connection:
        user = await connection.fetchrow(
            """
            SELECT * FROM users WHERE id_telegram = $1
            """,
            user_id
        )
    
    if user:
        user_info = ""
        fields = [
            ("ID", user['id_telegram']),
            ("Логин", f"@{user['tg_login']}" if user['tg_login'] else None),
            ("Имя", user['tg_firstname']),
            ("Фамилия", user['tg_lastname']),
            ("Время регистрации", user['registration_time']),
            ("Статус блокировки", user['status']),
            ("Дата оплаты", user['date_pay']),
            ("Дата окончания подписки", user['date_stop']),
            ("API ключ", user['bot_api']),
            ("Старый API ключ", user['old_bot_api']),
            ("Платежный ID Telegram", user['telegram_payment_charge_id']),
            ("Платежный ID провайдера", user['provider_payment_charge_id']),
            ("Оплачено", user['pay']),
            ("Напоминание за 5 дней", user['check_update']),
            ("Дата последнего обновления", user['date_pay'])
        ]

        for name, value in fields:
            if value not in [None, "", 0]:
                if isinstance(value, datetime):
                    value = value.strftime("%d.%m.%Y %H:%M")
                elif value == 1:
                    value = "Да"
                if name in ["Дата оплаты", "Дата окончания подписки", "Платежный ID Telegram", "Платежный ID провайдера", "Оплачено"]:
                    user_info += f"**{name}**: {value}\n"
                else:
                    user_info += f"{name}: {value}\n"

        status_icon = "✅" if user['status'] == 0 else "⛔️"
        status_text = f"{status_icon} Заблокировать" if user['status'] == 0 else f"{status_icon} Разблокировать"

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(status_text, callback_data=f"toggle_status_{user['id_telegram']}"))
        keyboard.add(types.InlineKeyboardButton("Назад", callback_data="back_to_users"))
        keyboard.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))
        
        await call.message.edit_text(user_info, reply_markup=keyboard)
        await state.update_data(user_id=user_id)
        await Form.user_detail.set()
    else:
        await call.message.answer("Пользователь не найден.", reply_markup=await get_admin_keyboard(call.from_user.id))

@dp.callback_query_handler(lambda c: c.data.startswith("toggle_status_"), state=Form.user_detail)
@admin_only
async def toggle_status(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[2])
    async with db_pool.acquire() as connection:
        user = await connection.fetchrow(
            """
            SELECT status FROM users WHERE id_telegram = $1
            """,
            user_id
        )
        if user:
            new_status = 1 if user['status'] == 0 else 0
            await connection.execute(
                """
                UPDATE users SET status = $1 WHERE id_telegram = $2
                """,
                new_status, user_id
            )
            status_icon = "✅" if new_status == 0 else "⛔️"
            status_text = f"{status_icon} Заблокировать" if new_status == 0 else f"{status_icon} Разблокировать"
            await call.message.edit_reply_markup(reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton(status_text, callback_data=f"toggle_status_{user_id}")
            ).add(
                types.InlineKeyboardButton("Назад", callback_data="back_to_users")
            ).add(
                types.InlineKeyboardButton("Закрыть", callback_data="close")
            ))
            await call.answer(f"Статус пользователя обновлен на {status_icon}.")
        else:
            await call.answer("Пользователь не найден.")


@dp.callback_query_handler(lambda c: c.data == "back_to_users", state=Form.user_detail)
@admin_only
async def back_to_users(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()
    await show_users_page(call.message, state)

@dp.callback_query_handler(lambda c: c.data == "close", state=[Form.user_page, Form.user_detail])
async def close_callback(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.delete()
    await call.answer()

# --- Функция подключения копий ботов -------------------------------------------------------------------------- #

# Проверка и запуск пользовательских ботов
async def start_user_bots():
    for filename in os.listdir(BASE_DIR):
        if filename.endswith("_bot_running.json"):
            user_id = filename.split("_")[0]
            user_dir = os.path.join(BASE_DIR, user_id)
            if os.path.isdir(user_dir):
                script_path = os.path.join(user_dir, 'start_user_bot.sh')
                process = subprocess.Popen(script_path, shell=True, executable='/bin/bash', preexec_fn=os.setsid)
                create_flag_file(user_id, process.pid)
                logging.info(f"Пользовательский бот {user_id} запущен с PID {process.pid}")

def create_flag_file(user_id, pid):
    flag_file = os.path.join(BASE_DIR, f'{user_id}_bot_running.json')
    with open(flag_file, 'w') as f:
        json.dump({'pid': pid}, f)

def delete_flag_file(user_id):
    flag_file = os.path.join(BASE_DIR, f'{user_id}_bot_running.json')
    if os.path.exists(flag_file):
        os.remove(flag_file)

def load_pid(user_id):
    flag_file = os.path.join(BASE_DIR, f'{user_id}_bot_running.json')
    if os.path.exists(flag_file):
        with open(flag_file, 'r') as f:
            data = json.load(f)
            return data['pid']
    return None

def is_user_bot_running(user_id):
    pid = load_pid(user_id)
    if pid:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True
    return False

async def get_user_api_key(user_id):
    async with db_pool.acquire() as connection:
        result = await connection.fetchval(
            "SELECT bot_api FROM users WHERE id_telegram = $1", user_id
        )
        return result

# Вывод инофрмации о запущенных пользовтаельских ботах
async def get_online_users():
    online_users = []
    async with db_pool.acquire() as connection:
        users = await connection.fetch("SELECT id_telegram, tg_login FROM users")
        for user in users:
            if is_user_bot_running(user['id_telegram']):
                online_users.append(user)
    return online_users

def get_online_users_keyboard(online_users):
    keyboard = types.InlineKeyboardMarkup()
    for user in online_users:
        button_text = f"@{user['tg_login']} | ID {user['id_telegram']}"
        callback_data = f"show_user_{user['id_telegram']}"
        keyboard.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    return keyboard

@dp.message_handler(lambda message: message.text == "Who Online?")
@admin_only
async def handle_online_users(message: types.Message):
    online_users = await get_online_users()
    if online_users:
        keyboard = get_online_users_keyboard(online_users)
        # Отправляем сообщение со списком ботов и клавиатурой
        await message.answer("Запущенные боты пользователей:", reply_markup=keyboard)
    else:
        await message.answer("Нет запущенных ботов пользователей.")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('show_user_'))
async def show_user_bot_info(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[-1])
    await bot.answer_callback_query(callback_query.id)
    
    # Получение информации о боте из базы данных
    async with db_pool.acquire() as connection:
        user_info = await connection.fetchrow(
            "SELECT tg_login, bot_api, date_stop FROM users WHERE id_telegram = $1", 
            user_id
        )
    
    if user_info:
        # Проверяем, есть ли API ключ
        bot_api = user_info['bot_api']
        if bot_api:
            # Создаём временного бота для получения информации о нём
            temp_bot = Bot(token=bot_api, proxy=TELEGRAM_PROXY)
            bot_info = await temp_bot.get_me()  # Получаем информацию о боте
            bot_username = bot_info.username
        else:
            bot_username = "Не установлен"
        
        # Формируем текст с информацией о боте
        bot_info_text = (
            f"Информация о боте пользователя:\n"
            f"Логин пользователя: @{user_info['tg_login']}\n"
            f"Логин бота: @{bot_username}\n"
            f"API ключ: {bot_api}\n"
            f"Подписка активна до: {user_info['date_stop'].strftime('%d.%m.%Y')}"
        )
        
        # Создаём клавиатуру с кнопкой "Остановить бота" и "Назад"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Остановить бота", callback_data=f"stop_user_{user_id}"))
        keyboard.add(types.InlineKeyboardButton("Назад", callback_data="back_to_users"))
    else:
        bot_info_text = "Информация о боте пользователя не найдена."
    
    # Редактируем текст в текущем сообщении
    await callback_query.message.edit_text(bot_info_text, reply_markup=keyboard)



@dp.callback_query_handler(lambda c: c.data and c.data.startswith('stop_user_'))
async def stop_user_bot_callback(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[-1])
    await bot.answer_callback_query(callback_query.id)
    
    # Попытка остановить бота
    try:
        pid = load_pid(user_id)
        if pid:
            # Останавливаем процесс бота
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            delete_flag_file(user_id)  # Удаление файла с PID
            await callback_query.message.answer(f"Бот пользователя {user_id} успешно остановлен.")
        else:
            await callback_query.message.answer(f"Не удалось найти запущенный процесс бота для пользователя {user_id}.")
        
        # Удаляем сообщение с информацией о пользователе после остановки бота
        await callback_query.message.delete()

    except OSError as e:
        await callback_query.message.answer(f"Ошибка при остановке бота пользователя {user_id}: {e}")


@dp.callback_query_handler(lambda c: c.data == "back_to_users")
async def back_to_online_users(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    # Вызов функции для отображения списка запущенных ботов
    online_users = await get_online_users()
    
    if online_users:
        keyboard = get_online_users_keyboard(online_users)
        # Редактируем текущее сообщение с новым списком ботов
        await callback_query.message.edit_text("Запущенные боты пользователей:", reply_markup=keyboard)
    else:
        await callback_query.message.edit_text("Нет запущенных ботов пользователей.")


#Декоратор проверки на pay=1

async def is_subscription_active(user_id):
    async with db_pool.acquire() as connection:
        result = await connection.fetchval(
            "SELECT pay FROM users WHERE id_telegram = $1", user_id
        )
        return result == 1

def subscription_required(handler):
    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = message.from_user.id
        subscription_active = await is_subscription_active(user_id)
        if not subscription_active:
            await message.answer("Ваша подписка не активна ❌")
            return
        await handler(message, *args, **kwargs)
    return wrapper

#Конец проверки на pay=1

async def test_api_key(api_key):
    try:
        test_bot = Bot(token=api_key, proxy=TELEGRAM_PROXY)
        session = await test_bot.get_session()
        bot_info = await test_bot.get_me()
    except Unauthorized:
        await session.close()  # Ensure the session is closed on exception
        return False, None
    await session.close()  # Ensure the session is closed on success
    return True, bot_info

async def start_user_bot(message: types.Message):
    user_id = message.from_user.id
    user_api_key = await get_user_api_key(user_id)  # Получение API ключа из базы данных
    
    if not user_api_key:
        await message.answer("Кажется, вы забыли указать API ключ вашего бота 🤭")
        return
    
    if is_user_bot_running(user_id):
        await message.answer("Ваш бот уже запущен ⚠️")
        return
    
    success, bot_info = await test_api_key(user_api_key)
    if not success:
        await message.answer("Неверный API ключ. Пожалуйста, проверьте его и попробуйте снова 🤔")
        return
    
    try:
        user_bot_dir = os.path.join(BASE_DIR, str(user_id))
        os.makedirs(user_bot_dir, exist_ok=True)
        
        # Копирование исходного файла в папку пользователя
        shutil.copy(SOURCE_SCRIPT, os.path.join(user_bot_dir, 'main.py'))
        _proxy_helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'telegram_proxy.py')
        if os.path.isfile(_proxy_helper):
            shutil.copy(_proxy_helper, os.path.join(user_bot_dir, 'telegram_proxy.py'))

        script_path = os.path.join(user_bot_dir, 'start_user_bot.sh')
        _tp_raw = (os.getenv('TELEGRAM_PROXY') or '').strip()
        _script_lines = ['#!/bin/bash']
        if _tp_raw:
            _script_lines.append(f'export TELEGRAM_PROXY={shlex.quote(_tp_raw)}')
        _script_lines.append(f'export API_KEY={shlex.quote(user_api_key)}')
        _script_lines.append('source /root/domastroi/venv/bin/activate')
        _script_lines.append(f'python {os.path.join(user_bot_dir, "main.py")}')
        with open(script_path, 'w') as file:
            file.write('\n'.join(_script_lines) + '\n')
        
        os.chmod(script_path, 0o755)
        
        user_bot_process = subprocess.Popen(script_path, shell=True, executable='/bin/bash', preexec_fn=os.setsid)
        
        create_flag_file(user_id, user_bot_process.pid)
        
        # Логирование информации о подключении
        logging.info(f"Пользователь {user_id} запустил бота с логином @{bot_info.username}")
        
        await message.answer("Ваш бот успешно запущен!")
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        await message.answer(f"Произошла ошибка при запуске бота: {e}")
        keyboard = get_user_bot_keyboard(user_id)
        await message.answer("Проверьте правильность вашего API ключа.", reply_markup=keyboard)

async def stop_user_bot(message: types.Message):
    user_id = message.from_user.id
    if not is_user_bot_running(user_id):
        await message.answer("Для активации нажмите «Запустить бота»")
        return
    
    try:
        pid = load_pid(user_id)
        if pid:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            delete_flag_file(user_id)
            logging.info(f"Пользователь {user_id} остановил бота")
            await message.answer("Ваш бот успешно остановлен 🚫")
        else:
            await message.answer("Не удалось получить PID процесса вашего бота.")
    except OSError as e:
        if e.errno == 3:  # No such process
            delete_flag_file(user_id)
            logging.info(f"Процесс бота пользователя {user_id} не найден, файл статуса удален.")
            await message.answer("Процесс не найден, удаляем файл статуса.")
        else:
            logging.error(f"Ошибка при остановке бота пользователя {user_id}: {e}")
            await message.answer(f"Произошла ошибка при остановке бота: {e}")


def get_user_bot_keyboard(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if is_user_bot_running(user_id):
        buttons = [
            ["Статус бота", "Остановить бота"],
            ["Назад в меню"]
        ]
    else:
        buttons = [
            ["Запустить бота"],
            ["Назад в меню"]
        ]
    for row in buttons:
        keyboard.add(*row)
    return keyboard

@dp.message_handler(lambda message: message.text == "Запуск 🤖")
@subscription_required
async def handle_start_bot(message: types.Message):
    user_id = message.from_user.id
    keyboard = get_user_bot_keyboard(user_id)
    await message.answer("Выберите действие:", reply_markup=keyboard)

    if is_user_bot_running(user_id):
        await message.answer("Ваш бот уже запущен ⚠️")
    else:
        await message.answer("Для активации нажмите «Запустить бота»")

@dp.message_handler(lambda message: message.text == "Запустить бота")
@subscription_required
async def handle_start_user_bot(message: types.Message):
    await start_user_bot(message)
    user_id = message.from_user.id
    keyboard = get_user_bot_keyboard(user_id)
    await message.answer("Выберите действие:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Статус бота")
@subscription_required
async def handle_user_bot_status(message: types.Message):
    user_id = message.from_user.id
    if is_user_bot_running(user_id):
        await message.answer("Ваш бот запущен ⚠️")
    else:
        await message.answer("Для активации нажмите «Запустить бота»")
    keyboard = get_user_bot_keyboard(user_id)
    await message.answer("Выберите действие:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Остановить бота")
@subscription_required
async def handle_stop_user_bot(message: types.Message):
    await stop_user_bot(message)
    user_id = message.from_user.id
    keyboard = get_user_bot_keyboard(user_id)
    await message.answer("Выберите действие:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Назад в меню")
async def handle_back(message: types.Message):
    # Возвращение в меню "Моя подписка"
    await my_subscription(message)

async def on_startup(dp):
    global db_pool
    db_pool = await create_db_pool()

# ----------------------------------------------------------------------------- #

async def start_polling_with_retry(dp, bot):
    while True:
        try:
            await dp.start_polling(bot)
        except TelegramAPIError as e:
            print(f"Ошибка API Telegram: {e}. Повторная попытка через 15 секунд...")
            await asyncio.sleep(15)

# Запуск асинхронной задачи вместе с ботом
async def on_startup(dp):
    global db_pool
    db_pool = await create_db_pool()
    asyncio.create_task(check_subscriptions())
    await start_user_bots()  # Запуск пользовательских ботов при старте

if __name__ == '__main__':
    start_polling(dp, skip_updates=True, on_startup=on_startup)
    asyncio.run(start_polling_with_retry(dp, bot))
