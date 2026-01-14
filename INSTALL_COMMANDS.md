# Команды для установки бота-опросника на VPS

## Предварительные требования

- Python 3.8+
- PostgreSQL
- Git
- sudo права

## Быстрая установка (автоматическая)

```bash
# Скачайте скрипт установки
wget https://raw.githubusercontent.com/SiteCraftorCPP/Domastroi_bot_admin2/main/INSTALL_VPS.sh

# Сделайте исполняемым
chmod +x INSTALL_VPS.sh

# Запустите
./INSTALL_VPS.sh
```

## Ручная установка (пошагово)

### 1. Создание структуры папок

```bash
# Создаем папку проекта (отдельно от других ботов)
sudo mkdir -p /opt/domastroi_bot
sudo mkdir -p /opt/domastroi_bot/bot
sudo mkdir -p /opt/domastroi_bot/user_bots

# Устанавливаем владельца (замените YOUR_USER)
sudo chown -R YOUR_USER:YOUR_USER /opt/domastroi_bot
```

### 2. Клонирование репозитория

```bash
cd /opt/domastroi_bot
git clone https://github.com/SiteCraftorCPP/Domastroi_bot_admin2.git .

# Копируем файлы бота
cp "Bot Files/test.py" bot/main.py
cp "Bot Files/questions.json" bot/questions.json
```

### 3. Создание виртуального окружения

```bash
cd /opt/domastroi_bot
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
cd "Bot Files"
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Создание файла .env

```bash
cd /opt/domastroi_bot/bot
nano .env
```

Содержимое `.env`:
```env
DB_USER=domastroi_admin_bot
DB_PASSWORD=ваш_пароль_бд
DB_NAME=domastroi_db
DB_HOST=localhost
DB_PORT=5432
```

Установите права:
```bash
chmod 600 .env
```

### 5. Настройка базы данных

```bash
# Войдите в PostgreSQL
sudo -u postgres psql

# Создайте пользователя и БД (если еще не созданы)
CREATE USER domastroi_admin_bot WITH PASSWORD 'ваш_пароль';
CREATE DATABASE domastroi_db OWNER domastroi_admin_bot;
GRANT ALL PRIVILEGES ON DATABASE domastroi_db TO domastroi_admin_bot;
\q

# Восстановите схему БД
cd /opt/domastroi_bot
psql -U domastroi_admin_bot -d domastroi_db -f dump.sql
```

### 6. Настройка данных пользователя в БД

**Важно:** Бот определяет ID пользователя по названию папки!

Если запускаете бота из папки `/opt/domastroi_bot/bot`, то в БД должна быть запись:

```sql
INSERT INTO users (id_telegram, bot_api, pay, date_stop) 
VALUES (0, 'ваш_токен_бота', 1, '2025-12-31 23:59:59');
```

**Или** создайте отдельную папку для каждого бота:

```bash
# Создаем папку с ID пользователя
mkdir -p /opt/domastroi_bot/user_bots/338566307
cd /opt/domastroi_bot/user_bots/338566307

# Копируем файлы
cp /opt/domastroi_bot/bot/main.py .
cp /opt/domastroi_bot/bot/questions.json .
cp /opt/domastroi_bot/bot/.env .

# В БД должна быть запись с id_telegram = 338566307
```

### 7. Создание systemd сервиса

```bash
sudo nano /etc/systemd/system/domastroi-bot.service
```

Содержимое (замените `YOUR_USER` на вашего пользователя):
```ini
[Unit]
Description=Domastroi Questionnaire Bot
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/opt/domastroi_bot/bot
Environment="PATH=/opt/domastroi_bot/venv/bin"
ExecStart=/opt/domastroi_bot/venv/bin/python /opt/domastroi_bot/bot/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Если используете отдельную папку для каждого бота:
```ini
[Unit]
Description=Domastroi Questionnaire Bot (User 338566307)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/opt/domastroi_bot/user_bots/338566307
Environment="PATH=/opt/domastroi_bot/venv/bin"
ExecStart=/opt/domastroi_bot/venv/bin/python /opt/domastroi_bot/user_bots/338566307/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 8. Запуск сервиса

```bash
# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable domastroi-bot

# Запускаем
sudo systemctl start domastroi-bot

# Проверяем статус
sudo systemctl status domastroi-bot
```

### 9. Просмотр логов

```bash
# Последние логи
sudo journalctl -u domastroi-bot -n 50

# Логи в реальном времени
sudo journalctl -u domastroi-bot -f

# Логи за сегодня
sudo journalctl -u domastroi-bot --since today
```

## Управление сервисом

```bash
# Остановить
sudo systemctl stop domastroi-bot

# Запустить
sudo systemctl start domastroi-bot

# Перезапустить
sudo systemctl restart domastroi-bot

# Статус
sudo systemctl status domastroi-bot

# Отключить автозапуск
sudo systemctl disable domastroi-bot
```

## Важные замечания

1. **Не конфликтует с другими ботами** - использует отдельную папку `/opt/domastroi_bot`
2. **Отдельное виртуальное окружение** - не влияет на другие проекты
3. **Отдельный systemd сервис** - можно запускать/останавливать независимо
4. **ID пользователя** - определяется по названию папки, где запущен бот
5. **Токен бота** - должен быть в БД в таблице `users`, поле `bot_api`

## Обновление бота

```bash
cd /opt/domastroi_bot
git pull
cp "Bot Files/test.py" bot/main.py
cp "Bot Files/questions.json" bot/questions.json
sudo systemctl restart domastroi-bot
```

## Устранение проблем

### Бот не запускается

```bash
# Проверьте логи
sudo journalctl -u domastroi-bot -n 100

# Проверьте .env файл
cat /opt/domastroi_bot/bot/.env

# Проверьте подключение к БД
psql -U domastroi_admin_bot -d domastroi_db -c "SELECT 1;"
```

### Ошибка "Токен бота не найден в базе данных"

Убедитесь, что:
1. В БД есть запись с `id_telegram` = названию папки
2. В поле `bot_api` указан правильный токен
3. Подписка активна: `pay = 1` и `date_stop` в будущем

### Ошибка подключения к БД

```bash
# Проверьте, запущен ли PostgreSQL
sudo systemctl status postgresql

# Проверьте настройки в .env
cat /opt/domastroi_bot/bot/.env

# Проверьте доступ
psql -U domastroi_admin_bot -d domastroi_db
```
