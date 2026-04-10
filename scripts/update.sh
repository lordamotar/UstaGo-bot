#!/bin/bash

# =================================================================
# 🔄 UstaGo - Скрипт обновления (Update & Deploy)
# Используется для ежедневного обновления кода и перезапуска
# =================================================================

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Пути
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT" || exit 1

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}    🔄 Обновление системы UstaGo...          ${NC}"
echo -e "${BLUE}==============================================${NC}"

# 1. Получение изменений
echo -e "${YELLOW}📥 1. Получение кода из Git...${NC}"
git pull origin main || { echo -e "${RED}❌ Ошибка git pull${NC}"; exit 1; }

# 2. Обновление Python зависимостей
echo -e "${YELLOW}🐍 2. Обновление Python зависимостей...${NC}"
if command -v uv &> /dev/null; then
    uv sync || { echo -e "${RED}❌ Ошибка uv sync${NC}"; exit 1; }
else
    source .venv/bin/activate && pip install -r requirements.txt
fi

# 3. Сборка фронтенда
echo -e "${YELLOW}🏗️ 3. Сборка Frontend (Next.js)...${NC}"
if [ -d "admin_frontend" ]; then
    cd admin_frontend || exit 1
    npm install --no-audit --no-fund
    npm run build || { echo -e "${RED}❌ Ошибка сборки!${NC}"; exit 1; }
    cd ..
fi

# 4. Перезапуск серверных процессов (PM2)
echo -e "${YELLOW}🚀 4. Перезапуск веб-сервисов (PM2)...${NC}"
if command -v pm2 &> /dev/null; then
    pm2 restart ustago-backend 2>/dev/null || pm2 start "uv run uvicorn admin_api.main:app --host 0.0.0.0 --port 8000" --name "ustago-backend"
    pm2 restart ustago-frontend 2>/dev/null || pm2 start npm --name "ustago-frontend" --cwd "$(pwd)/admin_frontend" -- start
    pm2 save
fi

# 5. Перезапуск Бота (Systemd)
echo -e "${YELLOW}🤖 5. Перезапуск Telegram Бота...${NC}"
if systemctl is-active --quiet ustago; then
    sudo systemctl restart ustago
    echo -e "${GREEN}✅ Бот перезапущен.${NC}"
else
    echo -e "${YELLOW}⚠️ Сервис бота не запущен. Попробуйте: sudo systemctl start ustago${NC}"
fi

echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!             ${NC}"
echo -e "${GREEN}==============================================${NC}"
