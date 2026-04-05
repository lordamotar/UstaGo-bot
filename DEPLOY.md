# 🚀 Инструкция по деплою (UstaGo Bot)

Это руководство поможет вам развернуть проект на Linux-сервере (Ubuntu/Debian) для постоянной работы.

## 📋 Предварительные требования

1. **VPS Сервер**: любая ОС семейства Linux (рекомендуется Ubuntu 22.04+).
2. **PostgreSQL**: база данных должна быть установлена и настроена.
3. **Python 3.10+**: можно использовать системный, но рекомендуется через `uv`.
4. **Бот**: токен от @BotFather.

---

## 🛠️ Шаг 1: Подготовка сервера

Обновите пакеты и установите зависимости:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential postgresql postgresql-contrib
```

Установите менеджер пакетов `uv` (самый быстрый способ управления Python):
```bash
curl -LsSf https://astral-sh/uv/install.sh | sh
source $HOME/.cargo/env
```

---

## 🐘 Шаг 2: Настройка базы данных

Войдите под пользователем `postgres` и создайте пользователя проекта:
```bash
sudo -u postgres psql
```

В консоли `psql` выполните:
```sql
CREATE DATABASE ustago_db;
CREATE USER ustago_admin WITH PASSWORD 'vash_slozhniy_parol';
GRANT ALL PRIVILEGES ON DATABASE ustago_db TO ustago_admin;
ALTER DATABASE ustago_db OWNER TO ustago_admin;
\q
```

---

## 📦 Шаг 3: Развертывание кода

Клонируйте проект в рабочую директорию (например, `/var/www` или вашу домашнюю):
```bash
git clone https://github.com/lordamotar/UstaGo-bot.git
cd UstaGo-bot
```

Создайте файл окружения `.env`:
```bash
nano .env
```

Вставьте в него свои данные:
```env
BOT_TOKEN=8763135642:AAE...ващ_токен
DATABASE_URL=postgresql+asyncpg://ustago_admin:vash_slozhniy_parol@localhost:5432/ustago_db
ADMIN_IDS=312082048,12345678
```

---

## 🚀 Шаг 4: Установка и запуск

Синхронизируйте зависимости и создайте виртуальное окружение через `uv`:
```bash
uv sync
```

**Инициализация базы данных (первый запуск):**
Настройте таблицы и первичные данные (категории, районы):
```bash
uv run python reset_db.py
```

---

## ⚙️ Шаг 5: Автозапуск через Systemd

Создайте конфиг сервиса, чтобы бот работал в фоне и перезапускался сам:
```bash
sudo nano /etc/systemd/system/ustago.service
```

Текст для файла (замените `USER` на ваше имя пользователя в Linux):
```ini
[Unit]
Description=UstaGo Telegram Bot Service
After=network.target postgresql.service

[Service]
User=USER
WorkingDirectory=/home/USER/UstaGo-bot
ExecStart=/home/USER/.cargo/bin/uv run python main.py
Restart=always
RestartSec=5
EnvironmentFile=/home/USER/UstaGo-bot/.env

[Install]
WantedBy=multi-user.target
```

**Запустите и включите сервис в автозагрузку:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable ustago
sudo systemctl start ustago
```

---

## 🔍 Полезные команды

- **Проверка логов в реальном времени:**
  ```bash
  sudo journalctl -u ustago -f
  ```
- **Перезагрузка бота:**
  ```bash
  sudo systemctl restart ustago
  ```
- **Остановка:**
  ```bash
  sudo systemctl stop ustago
  ```

---

*Создано для команды UstaGo. По всем вопросам — в профиль администратора.*
