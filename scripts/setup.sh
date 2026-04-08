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
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}Ошибка: Пожалуйста, не запускайте этот скрипт от root напрямую.${NC}"
   echo "Используйте обычного пользователя с правами sudo."
   exit 1
fi

# 2. Обновление системы и установка зависимостей
echo -e "${YELLOW}📦 Шаг 1: Обновление системы и установка пакетов...${NC}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential postgresql postgresql-contrib openssl

# 3. Установка uv (менеджер Python)
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}✨ Шаг 2: Установка uv...${NC}"
    curl -LsSf https://astral-sh/uv/install.sh | sh
    source $HOME/.cargo/env
else
    echo -e "${GREEN}✅ uv уже установлен.${NC}"
fi

# 4. Настройка PostgreSQL
echo -e "${YELLOW}🐘 Шаг 3: Настройка базы данных PostgreSQL...${NC}"
DB_NAME="ustago_db"
DB_USER="ustago_admin"
# Генерируем случайный пароль, если его нет
DB_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)

# Создаем БД и пользователя (игнорируем ошибки, если уже созданы)
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "База данных уже существует"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || echo "Пользователь базы данных уже существует"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null
sudo -u postgres psql -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;" 2>/dev/null

# 5. Проверка наличия .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📝 Шаг 4: Настройка переменных окружения (.env)...${NC}"
    echo -e "${YELLOW}Пожалуйста, введите данные бота:${NC}"
    read -p "Введите BOT_TOKEN (от @BotFather): " USER_BOT_TOKEN
    read -p "Введите ADMIN_IDS (через запятую, например 1234567,890123): " USER_ADMIN_IDS
    
    cat <<EOF > .env
BOT_TOKEN=$USER_BOT_TOKEN
DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
DB_USER=$DB_USER
DB_NAME=$DB_NAME
DB_PASS=$DB_PASS
DB_HOST=localhost
DB_PORT=5432
ADMIN_IDS=$USER_ADMIN_IDS
EOF
    echo -e "${GREEN}✅ Файл .env успешно создан.${NC}"
else
    echo -e "${GREEN}✅ Файл .env уже существует. Пропускаю настройку.${NC}"
fi

# 6. Установка зависимостей проекта
echo -e "${YELLOW}🐍 Шаг 5: Установка зависимостей через uv sync...${NC}"
uv sync

# 7. Инициализация базы данных
echo -e "${YELLOW}🏗 Шаг 6: Создание таблиц и начальных данных...${NC}"
uv run python reset_db.py

# 8. Настройка Systemd сервиса
echo -e "${YELLOW}⚙️ Шаг 7: Создание системного сервиса (ustago.service)...${NC}"
CUR_USER=$(whoami)
CUR_DIR=$(pwd)
SERVICE_FILE="/etc/systemd/system/ustago.service"

sudo bash -c "cat <<EOF > $SERVICE_FILE
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

echo -e "${YELLOW}🔄 Перезапуск системных служб...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable ustago
sudo systemctl restart ustago

echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}🎉 Деплой успешно завершен!                  ${NC}"
echo -e "${GREEN}==============================================${NC}"
echo -e "Бот запущен как сервис 'ustago'."
echo -e "Проверить статус: ${YELLOW}sudo systemctl status ustago${NC}"
echo -e "Проверить логи:   ${YELLOW}sudo journalctl -u ustago -f${NC}"
echo -e "=============================================="
