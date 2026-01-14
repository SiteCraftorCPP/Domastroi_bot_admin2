# Инструкция по настройке бота на VPS

## Необходимые данные для конфигурации

### 1. Файл .env

Создайте файл `.env` в папке `Bot Files/` со следующими переменными:

```env
# Токен админ-бота
BOT_API_TOKEN=ваш_токен_от_BotFather

# Токен для платежей Telegram
PAY_TOKEN=ваш_токен_платежей

# Цена подписки в копейках (10000 = 100 рублей)
PRICE=10000

# ID группы и канала (опционально, можно оставить пустыми)
GROUP_ID=-1001234567890
CHANNEL_ID=-1001234567890

# Настройки PostgreSQL
DB_USER=domastroi_admin_bot
DB_PASSWORD=ваш_пароль_бд
DB_NAME=domastroi_db
DB_HOST=localhost
DB_PORT=5432
```

### 2. Пути, которые нужно изменить в коде

В файле `Bot Files/main.py` на строках **94-95** жестко прописаны пути:

```python
BASE_DIR = '/root/domastroi/user_bots/'
SOURCE_SCRIPT = '/root/domastroi/test.py'
```

**Если ваши пути другие, измените их!**

Например:
```python
BASE_DIR = '/home/your_user/domastroi/user_bots/'
SOURCE_SCRIPT = '/home/your_user/domastroi/Bot Files/test.py'
```

Также на строке **1731** путь к виртуальному окружению:
```python
source /root/domastroi/venv/bin/activate
```

Замените на:
```python
source /home/your_user/domastroi/venv/bin/activate
```

### 3. Как получить необходимые токены

1. **BOT_API_TOKEN** - токен админ-бота:
   - Создайте бота через @BotFather
   - Скопируйте токен вида: `123456789:ABCdefGhIjKLmNoPQRstUVwXyZ`

2. **PAY_TOKEN** - токен для платежей:
   - Откройте @BotFather
   - Выберите `/mybots` -> выберите вашего бота
   - Выберите `Payments`
   - Следуйте инструкциям для настройки платежей
   - Скопируйте токен провайдера

3. **GROUP_ID и CHANNEL_ID** (если нужна обязательная подписка):
   - Добавьте бота в группу/канал как администратора
   - Используйте @userinfobot или API для получения ID
   - ID группы/канала имеет формат: `-1001234567890`

### 4. Настройка PostgreSQL

1. Установите PostgreSQL на VPS:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

2. Создайте базу данных:
```bash
sudo -u postgres psql
CREATE USER domastroi_admin_bot WITH PASSWORD 'ваш_пароль';
CREATE DATABASE domastroi_db OWNER domastroi_admin_bot;
GRANT ALL PRIVILEGES ON DATABASE domastroi_db TO domastroi_admin_bot;
\q
```

3. Восстановите схему БД из dump.sql:
```bash
psql -U domastroi_admin_bot -d domastroi_db -f dump.sql
```

### 5. Структура папок на VPS

Рекомендуемая структура:
```
/root/domastroi/
├── Bot Files/
│   ├── main.py
│   ├── test.py
│   ├── questions.json
│   ├── requirements.txt
│   └── .env
├── user_bots/          # Создается автоматически
│   └── {user_id}/
│       ├── main.py
│       ├── start_user_bot.sh
│       └── data_questions/
└── venv/               # Виртуальное окружение
```

### 6. Установка зависимостей

```bash
cd /root/domastroi
python3 -m venv venv
source venv/bin/activate
cd "Bot Files"
pip install -r requirements.txt
```

### 7. Запуск бота

Для постоянной работы используйте systemd или supervisor:

**systemd** (создайте файл `/etc/systemd/system/domastroi-bot.service`):
```ini
[Unit]
Description=Domastroi Admin Bot
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/domastroi/Bot Files
Environment="PATH=/root/domastroi/venv/bin"
ExecStart=/root/domastroi/venv/bin/python /root/domastroi/Bot Files/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable domastroi-bot
sudo systemctl start domastroi-bot
```

### 8. Проверка работы

Проверьте логи:
```bash
sudo systemctl status domastroi-bot
journalctl -u domastroi-bot -f
```

Или если запускаете напрямую:
```bash
cd "/root/domastroi/Bot Files"
source /root/domastroi/venv/bin/activate
python main.py
```

### 9. Важные замечания

- ✅ Убедитесь, что все пути в коде соответствуют реальным путям на VPS
- ✅ Проверьте права доступа на папки (особенно для `user_bots/`)
- ✅ Файл `.env` должен быть защищен (права 600: `chmod 600 .env`)
- ✅ Убедитесь, что PostgreSQL запущен: `sudo systemctl status postgresql`
- ✅ Проверьте, что порты открыты (если БД на другом сервере)
- ✅ Для работы платежей нужно настроить провайдера в @BotFather
