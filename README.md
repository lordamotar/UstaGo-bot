# UstaGo Bot (Marketplace)

Инновационный Telegram-бот для поиска мастеров и управления заказами.

## 🌟 Основные возможности
- **Для заказчиков**: Быстрое создание заявок, выбор категорий, уведомления об откликах.
- **Для мастеров**: Профессиональный профиль, фильтрация заказов по районам и категориям, система баланса.
- **Для админов**: Полная панель управления (Next.js), статистика, модерация пользователей и финансов.

## 🚀 Технологический стек
- **Bot**: Python 3.10+, `aiogram 3.x`
- **Database**: PostgreSQL + `SQLAlchemy` (Async)
- **Admin Panel**: 
  - Backend: FastAPI
  - Frontend: Next.js + TailwindCSS + Lucide
- **Infrastructure**: PM2, Systemd, nginx

## 📦 Быстрый старт на сервере

1. Клонируйте репозиторий:
```bash
git clone https://github.com/lordamotar/UstaGo-bot.git
cd UstaGo-bot
```

2. Запустите установку:
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

3. Для последующих обновлений используйте:
```bash
./deploy.sh
```

## 📜 Документация
- [Инструкция по деплою](DEPLOY.md)
- [Техническое задание (PRD)](docs/prds/)
- [Структура базы данных](database/models.py)

---
© 2024 UstaGo Team
