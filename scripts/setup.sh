#!/bin/bash

# =================================================================
# 🚀 UstaGo Bot - Автоматический скрипт деплоя
# Поддерживаемые ОС: Ubuntu 22.04+, Debian 11+
# =================================================================

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}    🤖 UstaGo Bot Deployment Utility         ${NC}"
echo -e "${BLUE}==============================================${NC}"

# 1. Проверка прав (не запускать от root напрямую, скрипт использует sudo)

# 2. Обновление системы и установка зависимостей
echo -e "${YELLOW}📦 Шаг 1: Обновление системы и установка пакетов...${NC}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential postgresql postgresql-contrib openssl

# 3. Установка Node.js 20 и PM2
echo -e "${YELLOW}🟢 Шаг 2: Установка Node.js 20 и PM2...${NC}"
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi
sudo npm install -g pm2

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}✨ Шаг 3: Установка uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
else
    echo -e "${GREEN}✅ uv уже установлен.${NC}"
fi

# 5. Настройка PostgreSQL
echo -e "${YELLOW}🐘 Шаг 4: Настройка базы данных PostgreSQL...${NC}"
DB_NAME="ustago_db"
DB_USER="ustago_admin"
DB_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)

sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "База данных уже существует"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || echo "Пользователь базы данных уже существует"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null

# 6. Определение IP и настройка .env
SERVER_IP=$(curl -4 -s https://ifconfig.me)
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📝 Шаг 5: Настройка переменных окружения...${NC}"
    read -p "Введите BOT_TOKEN (от @BotFather): " USER_BOT_TOKEN
    
    cat <<EOF > .env
BOT_TOKEN=$USER_BOT_TOKEN
DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
ADMIN_IDS=
SENTRY_DSN=
EOF
fi

# Настройка фронтенда
echo "NEXT_PUBLIC_API_URL=http://$SERVER_IP:8000/api/v1" > admin_frontend/.env.local
sed -i "s/127.0.0.1/$SERVER_IP/g" admin_frontend/src/lib/api.ts

# 7. Установка зависимостей и сборка
echo -e "${YELLOW}📦 Шаг 6: Установка зависимостей и сборка...${NC}"
uv sync
uv run alembic upgrade head

if [ -d "admin_frontend" ]; then
    cd admin_frontend
    npm install
    npm run build
    cd ..
fi

# 8. Настройка PM2 и Systemd
echo -e "${YELLOW}🚀 Шаг 7: Запуск сервисов...${NC}"
# Backend
pm2 start "uv run uvicorn admin_api.main:app --host 0.0.0.0 --port 8000" --name "ustago-backend"
# Frontend
pm2 start "npm run start" --name "ustago-frontend" --cwd "$(pwd)/admin_frontend"
pm2 save

# Bot (Systemd)
CUR_USER=$(whoami)
CUR_DIR=$(pwd)
sudo bash -c "cat <<EOF > /etc/systemd/system/ustago.service
[Unit]
Description=UstaGo Telegram Bot Service
After=network.target postgresql.service

[Service]
User=$CUR_USER
WorkingDirectory=$CUR_DIR
ExecStart=$CUR_DIR/.venv/bin/python main.py
Restart=always
RestartSec=5
EnvironmentFile=$CUR_DIR/.env

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable ustago
sudo systemctl restart ustago

echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}🎉 УСТАНОВКА ЗАВЕРШЕНА!                      ${NC}"
echo -e "${GREEN}==============================================${NC}"
echo -e "Админка: http://$SERVER_IP:3000"
echo -e "API:     http://$SERVER_IP:8000"
echo -e "=============================================="
