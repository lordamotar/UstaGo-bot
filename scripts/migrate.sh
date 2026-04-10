#!/bin/bash

# =================================================================
# 🏗️ UstaGo - Скрипт миграции базы данных
# Используется только при изменении структуры таблиц
# =================================================================

# Цвета
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT" || exit 1

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}    🏗️ Применение миграций базы данных...    ${NC}"
echo -e "${BLUE}==============================================${NC}"

if command -v uv &> /dev/null; then
    uv run alembic upgrade head
else
    source .venv/bin/activate && alembic upgrade head
fi

echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}✅ База данных успешно обновлена!           ${NC}"
echo -e "${GREEN}==============================================${NC}"
