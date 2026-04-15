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
# Сохраняем локальные изменения (api.ts, .env), если они есть
git stash save "Autostash before update" --quiet
git pull origin main --rebase || { 
    echo -e "${RED}❌ Ошибка git pull. Проверьте конфликты вручную.${NC}"; 
    git stash pop --quiet
    exit 1; 
}
# Возвращаем локальные изменения
git stash pop --quiet 2>/dev/null

# 2. Обновление Python зависимостей
echo -e "${YELLOW}🐍 2. Обновление Python зависимостей...${NC}"
if command -v uv &> /dev/null; then
    uv sync || { echo -e "${RED}❌ Ошибка uv sync${NC}"; exit 1; }
else
    source .venv/bin/activate && pip install -r requirements.txt
fi

# 3. Применение миграций базы данных
echo -e "${YELLOW}🏗️ 3. Обновление структуры базы данных (Alembic)...${NC}"
if command -v uv &> /dev/null; then
    uv run alembic upgrade head || { echo -e "${RED}❌ Ошибка миграции!${NC}"; exit 1; }
else
    source .venv/bin/activate && alembic upgrade head || { echo -e "${RED}❌ Ошибка миграции!${NC}"; exit 1; }
fi

# 4. Сборка фронтенда
echo -e "${YELLOW}🏗️ 4. Сборка Frontend (Next.js)...${NC}"
if [ -d "admin_frontend" ]; then
    cd admin_frontend || exit 1
    npm install --no-audit --no-fund
    npm run build || { echo -e "${RED}❌ Ошибка сборки!${NC}"; exit 1; }
    cd ..
fi

# 5. Перезапуск серверных процессов (PM2)
echo -e "${YELLOW}🚀 5. Перезапуск веб-сервисов (PM2)...${NC}"
if command -v pm2 &> /dev/null; then
    # Backend
    pm2 restart ustago-backend 2>/dev/null || pm2 start "uv run uvicorn admin_api.main:app --host 0.0.0.0 --port 8000" --name "ustago-backend"
    
    # Frontend
    pm2 restart ustago-frontend 2>/dev/null || pm2 start "npm run start" --name "ustago-frontend" --cwd "$(pwd)/admin_frontend"
    
    pm2 save
fi

# 6. Перезапуск Бота (Systemd)
echo -e "${YELLOW}🤖 6. Перезапуск Telegram Бота...${NC}"
if systemctl list-unit-files | grep -q ustago.service; then
    sudo systemctl restart ustago
    echo -e "${GREEN}✅ Бот перезапущен.${NC}"
else
    echo -e "${YELLOW}⚠️ Сервис бота не найден (ustago.service). Пропускаю...${NC}"
fi

echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!             ${NC}"
echo -e "${GREEN}==============================================${NC}"
