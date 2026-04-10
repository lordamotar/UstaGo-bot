#!/bin/bash

echo "🔄 Начинаем обновление UstaGo с GitHub..."
git pull origin main

echo "📦 Устанавливаем зависимости для Frontend (Next.js)..."
cd admin_frontend
npm install

echo "🏗️ Собираем production-версию Frontend..."
npm run build
cd ..

echo "Проверка наличия PM2 (менеджер процессов)..."
if ! command -v pm2 &> /dev/null
then
    echo "⚙️ Устанавливаем PM2 глобально..."
    sudo npm install -g pm2
fi

echo "🚀 Запускаем Backend (FastAPI)..."
# Останавливаем старый процесс если есть
pm2 stop ustago-backend 2>/dev/null
pm2 delete ustago-backend 2>/dev/null
# Запускаем FastAPI через pm2
pm2 start "uv run uvicorn admin_api.main:app --host 0.0.0.0 --port 8000" --name "ustago-backend"

echo "🚀 Запускаем Frontend (Next.js)..."
cd admin_frontend
pm2 stop ustago-frontend 2>/dev/null
pm2 delete ustago-frontend 2>/dev/null
# Запускаем собранный Next.js с явным указанием рабочей папки
pm2 start npm --name "ustago-frontend" --cwd "$(pwd)" -- start

# Сохраняем текущие процессы, чтобы они сами запускались при перезагрузке сервера (reboot)
pm2 save

echo "✅ ГОТОВО! Админ-панель успешно запущена и теперь работает в фоне."
echo "🌐 Откройте в браузере: http://ВАШ_IP_СЕРВЕРА:3000"
echo "📊 Логи можно смотреть командами:"
echo "   pm2 logs ustago-backend"
echo "   pm2 logs ustago-frontend"
