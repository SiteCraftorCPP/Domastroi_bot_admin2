#!/bin/bash

# ============================================
# УСТАНОВКА БОТА-ОПРОСНИКА НА VPS
# ============================================

set -e  # Остановка при ошибке

echo "🚀 Начинаем установку бота-опросника..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================
# 1. СОЗДАНИЕ СТРУКТУРЫ ПАПОК
# ============================================

PROJECT_DIR="/opt/domastroi_bot"
VENV_DIR="$PROJECT_DIR/venv"
BOT_DIR="$PROJECT_DIR/bot"

echo -e "${YELLOW}📁 Создаем структуру папок...${NC}"
sudo mkdir -p "$PROJECT_DIR"
sudo mkdir -p "$BOT_DIR"
sudo mkdir -p "$PROJECT_DIR/user_bots"

# Устанавливаем владельца (замените YOUR_USER на вашего пользователя)
# Если запускаете от root, уберите sudo
sudo chown -R $USER:$USER "$PROJECT_DIR"

# ============================================
# 2. КЛОНИРОВАНИЕ РЕПОЗИТОРИЯ
# ============================================

echo -e "${YELLOW}📥 Клонируем репозиторий...${NC}"
cd "$PROJECT_DIR"
if [ -d ".git" ]; then
    echo "Репозиторий уже существует, обновляем..."
    git pull
else
    git clone https://github.com/SiteCraftorCPP/Domastroi_bot_admin2.git .
fi

# Копируем необходимые файлы
cp "Bot Files/test.py" "$BOT_DIR/main.py"
cp "Bot Files/questions.json" "$BOT_DIR/questions.json"

# ============================================
# 3. СОЗДАНИЕ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ
# ============================================

echo -e "${YELLOW}🐍 Создаем виртуальное окружение...${NC}"
cd "$PROJECT_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Устанавливаем зависимости
echo -e "${YELLOW}📦 Устанавливаем зависимости...${NC}"
pip install --upgrade pip
cd "Bot Files"
pip install -r requirements.txt

# ============================================
# 4. СОЗДАНИЕ ФАЙЛА .env
# ============================================

echo -e "${YELLOW}⚙️  Создаем файл .env...${NC}"
cd "$BOT_DIR"

if [ ! -f ".env" ]; then
    cat > .env << EOF
# Настройки PostgreSQL
DB_USER=domastroi_admin_bot
DB_PASSWORD=ВАШ_ПАРОЛЬ_БД
DB_NAME=domastroi_db
DB_HOST=localhost
DB_PORT=5432
EOF
    chmod 600 .env
    echo -e "${GREEN}✅ Файл .env создан. Не забудьте заполнить данные БД!${NC}"
else
    echo "Файл .env уже существует, пропускаем..."
fi

# ============================================
# 5. НАСТРОЙКА БАЗЫ ДАННЫХ
# ============================================

echo -e "${YELLOW}🗄️  Настройка базы данных...${NC}"
echo "Если БД еще не создана, выполните:"
echo "  sudo -u postgres psql"
echo "  CREATE USER domastroi_admin_bot WITH PASSWORD 'ваш_пароль';"
echo "  CREATE DATABASE domastroi_db OWNER domastroi_admin_bot;"
echo "  GRANT ALL PRIVILEGES ON DATABASE domastroi_db TO domastroi_admin_bot;"
echo ""
echo "Затем восстановите схему:"
echo "  psql -U domastroi_admin_bot -d domastroi_db -f $PROJECT_DIR/dump.sql"

# ============================================
# 6. СОЗДАНИЕ SYSTEMD СЕРВИСА
# ============================================

echo -e "${YELLOW}🔧 Создаем systemd сервис...${NC}"

# Определяем пользователя
SERVICE_USER=$(whoami)
if [ "$EUID" -eq 0 ]; then
    SERVICE_USER="root"
fi

cat > /tmp/domastroi-bot.service << EOF
[Unit]
Description=Domastroi Questionnaire Bot
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python $BOT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/domastroi-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

echo -e "${GREEN}✅ Systemd сервис создан${NC}"

# ============================================
# 7. ИНСТРУКЦИИ ПО ЗАПУСКУ
# ============================================

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Установка завершена!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📝 Следующие шаги:"
echo ""
echo "1. Отредактируйте файл .env:"
echo "   nano $BOT_DIR/.env"
echo ""
echo "2. Убедитесь, что в БД есть запись пользователя:"
echo "   - id_telegram = ID папки (название папки, где запущен бот)"
echo "   - bot_api = токен бота от @BotFather"
echo "   - pay = 1 (подписка активна)"
echo ""
echo "3. Если используете отдельную папку для каждого бота, создайте структуру:"
echo "   mkdir -p $PROJECT_DIR/user_bots/{USER_ID}"
echo "   cp $BOT_DIR/main.py $PROJECT_DIR/user_bots/{USER_ID}/"
echo "   cp $BOT_DIR/questions.json $PROJECT_DIR/user_bots/{USER_ID}/"
echo "   cd $PROJECT_DIR/user_bots/{USER_ID}"
echo "   # Создайте .env с настройками БД"
echo ""
echo "4. Запустите сервис:"
echo "   sudo systemctl enable domastroi-bot"
echo "   sudo systemctl start domastroi-bot"
echo ""
echo "5. Проверьте статус:"
echo "   sudo systemctl status domastroi-bot"
echo "   sudo journalctl -u domastroi-bot -f"
echo ""
echo "6. Для остановки:"
echo "   sudo systemctl stop domastroi-bot"
echo ""
