#!/bin/bash

# =================================================================
# 🔄 UstaGo Bot - Скрипт быстрого обновления
# =================================================================

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Обновление бота UstaGo...${NC}"

# 1. Pull changes
echo -e "${YELLOW}📥 Получение изменений из Git...${NC}"
git pull

# 2. Sync dependencies
echo -e "${YELLOW}🐍 Обновление зависимостей...${NC}"
uv sync

# 3. Optional: Migrations (if you use alembic)
# echo -e "${YELLOW} Alembic migrations...${NC}"
# uv run alembic upgrade head

# 4. Restart service
echo -e "${YELLOW}🔄 Перезагрузка сервиса...${NC}"
sudo systemctl restart ustago

echo -e "${GREEN}✅ Обновление завершено!${NC}"
sudo systemctl status ustago --no-pager
