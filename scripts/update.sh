#!/bin/bash

# =================================================================
# 🔄 UstaGo Bot - Скрипт быстрого обновления
# Просто запускает основной деплой-скрипт
# =================================================================

# Получаем путь к директории скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/.."

cd "$PROJECT_ROOT" || exit 1

if [ -f "./deploy.sh" ]; then
    chmod +x ./deploy.sh
    ./deploy.sh
else
    echo "❌ Ошибка: Файл deploy.sh не найден в корне проекта!"
    exit 1
fi
