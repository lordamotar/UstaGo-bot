#!/bin/bash

# ==============================================================================
# 📦 UstaGo Database Backup Script
# ==============================================================================

# Загрузка переменных окружения из .env
set -a
source .env
set +a

# Конфигурация
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/ustago_db_$TIMESTAMP.sql"
ZIP_FILE="$BACKUP_FILE.gz"
RETENTION_DAYS=7

# Создание папки, если её нет
mkdir -p "$BACKUP_DIR"

echo "🚀 Начинаю резервное копирование базы данных..."

# Выполнение дампа (используем PGPASSWORD для автоматизации)
# Формат: postgresql://user:pass@host:port/dbname
export PGPASSWORD=$DB_PASS
pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Дамп успешно создан: $BACKUP_FILE"
    
    # Сжатие
    gzip "$BACKUP_FILE"
    echo "📦 Файл сжат: $ZIP_FILE"
    
    # Удаление старых бэкапов
    echo "🧹 Очистка старых бэкапов (старше $RETENTION_DAYS дней)..."
    find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
    
    echo "✨ Резервное копирование завершено успешно!"
else
    echo "❌ Ошибка при создании дампа!"
    exit 1
fi
