#!/bin/bash

# =================================================================
# 🚀 UstaGo - Скрипт полного обновления и деплоя
# Обновляет Бот, API и Админ-панель
# =================================================================

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}    🔄 Обновление системы UstaGo...          ${NC}"
echo -e "${BLUE}==============================================${NC}"

# 1. Получение изменений из Git
echo -e "${YELLOW}📥 Шаг 1: Получение изменений из GitHub...${NC}"
git pull origin main || { echo -e "${RED}❌ Ошибка git pull${NC}"; exit 1; }

# 2. Обновление зависимостей Bot/API
echo -e "${YELLOW}🐍 Шаг 2: Обновление Python зависимостей (uv)...${NC}"
if command -v uv &> /dev/null; then
    uv sync || { echo -e "${RED}❌ Ошибка uv sync${NC}"; exit 1; }
else
    echo -e "${YELLOW}⚠️ uv не найден, пробую через pip...${NC}"
    source .venv/bin/activate && pip install -r requirements.txt
fi

# 3. Миграции базы данных (если есть)
# echo -e "${YELLOW}🏗️ Шаг 3: Применение миграций...${NC}"
# uv run alembic upgrade head

# 4. Сборка фронтенда
echo -e "${YELLOW}🏗️ Шаг 4: Сборка Frontend (Next.js)...${NC}"
cd admin_frontend || exit 1

echo "📦 Установка npm зависимостей..."
npm install --no-audit --no-fund || { echo -e "${RED}❌ Ошибка npm install${NC}"; exit 1; }

echo "🔨 Сборка production-билда..."
# Мы запускаем билд и проверяем его успех. Если билд упал (например, ошибка TS), мы НЕ перезапускаем сервер.
npm run build || { 
    echo -e "${RED}❌ Ошибка сборки фронтенда! Проверьте TypeScript ошибки выше.${NC}"; 
    echo -e "${YELLOW}💡 Подсказка: Часто ошибка в 'str' вместо 'string' или импортах.${NC}";
    exit 1; 
}
cd ..

# 5. Проверка PM2
if ! command -v pm2 &> /dev/null; then
    echo -e "${YELLOW}⚙️ Установка PM2...${NC}"
    sudo npm install -g pm2
fi

# 6. Перезапуск компонентов через PM2
echo -e "${YELLOW}🚀 Шаг 5: Перезапуск API и Frontend через PM2...${NC}"

# Backend API
pm2 stop ustago-backend 2>/dev/null
pm2 delete ustago-backend 2>/dev/null
pm2 start "uv run uvicorn admin_api.main:app --host 0.0.0.0 --port 8000" --name "ustago-backend"

# Frontend (Важно: указываем --cwd)
pm2 stop ustago-frontend 2>/dev/null
pm2 delete ustago-frontend 2>/dev/null
# Используем прямой запуск через рабочую директорию
pm2 start npm --name "ustago-frontend" --cwd "$(pwd)/admin_frontend" -- start

# Сохраняем конфиг PM2
pm2 save

# 7. Перезапуск Бота (через systemd)
echo -e "${YELLOW}🤖 Шаг 6: Перезапуск Telegram Бота...${NC}"
if systemctl is-active --quiet ustago; then
    sudo systemctl restart ustago
    echo -e "${GREEN}✅ Бот перезапущен.${NC}"
else
    echo -e "${YELLOW}⚠️ Сервис ustago не найден или не активен. Пробую запустить...${NC}"
    sudo systemctl enable ustago 2>/dev/null
    sudo systemctl start ustago 2>/dev/null
fi

echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}🎉 ВСЕОБЩЕЕ ОБНОВЛЕНИЕ ЗАВЕРШЕНО!            ${NC}"
echo -e "${GREEN}==============================================${NC}"
echo -e "📊 Статус PM2:"
pm2 status
echo -e "🌐 Админка (Frontend): http://ВАШ_IP:3000"
echo -e "🖥️ API (Backend):      http://ВАШ_IP:8000/docs"
echo -e "💬 Бот:                Проверьте в Telegram"
echo -e "=============================================="
