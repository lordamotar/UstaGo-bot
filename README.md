# UstaGo Bot (Marketplace)

Инновационный Telegram-бот для поиска мастеров и управления заказами с мощной панелью управления.

## 🌟 Основные возможности
- **Безопасность**: Двухфакторная аутентификация (2FA) через Telegram для входа в админку, блокировка после неудачных попыток, роли админов (суперадмин / модератор / финансист).
- **Аудит**: Полное логирование действий администраторов (кто, когда и что изменил).
- **Ошибка-менеджмент**: Интеграция с Sentry для отслеживания багов в реальном времени.
- **Для заказчиков**: Быстрое создание заявок, выбор категорий, уведомления об откликах.
- **Для мастеров**: Профессиональный профиль, фильтрация заказов по районам и категориям, система баланса.
- **Для админов**: Современный дашборд с аналитикой и воронкой заявок, поиск и экспорт пользователей и заказов, обращения в поддержку, учёт источников пользователей (реферальные и рекламные ссылки), модерация, финансы и справочники.

## 🚀 Технологический стек
- **Bot**: Python 3.12+, `aiogram 3.x`
- **Database**: PostgreSQL + `SQLAlchemy` (Async) + `Alembic`
- **Admin Panel**: 
  - Backend: FastAPI
  - Frontend: Next.js + TailwindCSS + Lucide + Recharts
- **Infrastructure**: PM2, Systemd, Redis, nginx, `uv`

## ⚙️ Настройка (.env)
Скопируйте `.env.example` в `.env` и заполните. Обязательны `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS` и `JWT_SECRET_KEY`
(не короче 32 символов; `setup.sh` и `update.sh` создают его сами, если его нет). `CORS_ORIGINS` — адрес, по которому открывается панель
(например, `https://admin.example.com`), `REDIS_URL` — Redis для диалогов бота и защиты входа.

## 📦 Управление проектом

Все действия по управлению проектом теперь вынесены в папку `scripts/` для безопасности и удобства:

1. **Первичная установка**:
```bash
bash scripts/setup.sh
```

2. **Обновление кода (деплой)** — безопасно, с дампом базы и проверками (рекомендуется):
```bash
bash scripts/safe_update.sh          # --check: только показать, что изменится; --yes: без вопроса
bash scripts/rollback.sh             # если что-то пошло не так (--with-db вернёт и базу из дампа)
```
   Быстрый вариант без дампа и проверок: `bash scripts/update.sh`.

3. **Миграции базы данных** (если изменилась структура):
```bash
bash scripts/migrate.sh
```

## ⚡️ Запуск проекта (Frontend, Backend, Bot)

### 🛠️ 1. Локальная разработка (Development)

#### 🔹 Установка зависимостей и база данных
```bash
# Установка Python-зависимостей через uv
uv sync

# Применение миграций БД
uv run alembic upgrade head

# (Опционально) Создание администратора админ-панели
PYTHONPATH=. uv run python scripts/set_admin.py <логин> <надёжный_пароль>
```

#### 🔹 1. Запуск Backend (Admin API - FastAPI)
```bash
uv run uvicorn admin_api.main:app --reload --port 8000
```
> API доступен по адресу: `http://localhost:8000/docs`

#### 🔹 2. Запуск Frontend (Admin Panel - Next.js)
```bash
cd admin_frontend
npm install
npm run dev
```
> Фронтенд доступен по адресу: `http://localhost:3000`

#### 🔹 3. Запуск Telegram Бота
```bash
uv run python main.py
```

---

### 🚀 2. Запуск на сервере (Ubuntu 22.04 / 24.04)

> ⚠️ **ВАЖНО**: Обязательно перейдите в папку проекта перед запуском команд: `cd ~/ustago-bot`

#### 🔹 2.1 Первичная установка системных пакетов
```bash
# Обновление пакетов Ubuntu
sudo apt update && sudo apt upgrade -y

# Установка системных зависимостей и PostgreSQL
sudo apt install -y git curl build-essential postgresql postgresql-contrib redis-server openssl
sudo systemctl enable --now redis-server

# Установка Node.js 20 и PM2
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

# Установка Python пакетного менеджера uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

#### 🔹 2.2 Быстрая автоматическая установка проекта
```bash
cd ~/ustago-bot
bash scripts/setup.sh
```

#### 🔹 2.3 Автоматический деплой / обновление кода
```bash
cd ~/ustago-bot
bash scripts/safe_update.sh
```

`safe_update.sh` по шагам: проверки (диск, база, Redis) → дамп базы в `~/ustago_backups/` с проверкой → показ новых коммитов и вопрос →
`update.sh` (код, зависимости, миграции, сборка панели, перезапуск) → проверки после (версия миграций, число пользователей, процессы PM2, бот, API, ошибки в логе).
При сбое откат: `bash scripts/rollback.sh` (только код; база не трогается) или `bash scripts/rollback.sh --with-db` (код и база из дампа, данные после дампа пропадут).
Быстрое обновление без дампа и проверок — `bash scripts/update.sh`.

#### 🔹 2.4 Ручные команды управления сервисами (Ubuntu)

```bash
# Перейти в папку проекта
cd ~/ustago-bot

# При необходимости очистить старые дубликаты процессов в PM2
pm2 delete all
```

* **Управление Backend (FastAPI):**
  ```bash
  # Запуск
  pm2 start "uv run uvicorn admin_api.main:app --host 0.0.0.0 --port 8000" --name "ustago-backend"
  # Перезапуск
  pm2 restart ustago-backend
  # Просмотр логов
  pm2 logs ustago-backend
  ```

* **Управление Frontend (Next.js):**
  ```bash
  # Сборка и запуск
  cd admin_frontend && npm run build && cd ..
  pm2 start "npm run start" --name "ustago-frontend" --cwd "$(pwd)/admin_frontend"
  # Перезапуск
  pm2 restart ustago-frontend
  # Просмотр логов
  pm2 logs ustago-frontend
  ```

* **Управление Telegram Ботом (Systemd):**
  ```bash
  # Старт / Перезапуск
  sudo systemctl restart ustago
  # Статус службы
  sudo systemctl status ustago
  # Просмотр логов в реальном времени
  sudo journalctl -u ustago -f
  ```

* **Сохранение конфигурации PM2 (чтобы автозапускалось при перезагрузке сервера):**
  ```bash
  pm2 save
  pm2 startup   # выведет команду «sudo env PATH=... pm2 startup systemd ...» — выполните её один раз
  ```

---

## 📜 Документация
- [🚀 Подробная инструкция по деплою](DEPLOY.md)
- [📝 Техническое задание (PRD)](docs/prds/)
- [🛠️ Админ-панель: роли, защита входа, возможности](docs/ADMIN_PANEL.md)
- [🗄️ Схема базы данных](database/models.py)

## 🛠️ Сводный мониторинг сервисов
| Компонент | Просмотр логов | Перезапуск |
| :--- | :--- | :--- |
| **Telegram Бот** | `sudo journalctl -u ustago -f` | `sudo systemctl restart ustago` |
| **Admin API** | `pm2 logs ustago-backend` | `pm2 restart ustago-backend` |
| **Admin Panel** | `pm2 logs ustago-frontend` | `pm2 restart ustago-frontend` |

### Рекомендованное обновление (Deploy)
Запускайте после каждого `git push` из локальной среды:
```bash
bash scripts/update.sh
```

### Сброс пароля администратора
Если вы забыли пароль или не можете войти в админку:
```bash
PYTHONPATH=. uv run python scripts/set_admin.py <логин> <пароль> [superadmin|moderator|finance]
```
Третий параметр — роль в панели (по умолчанию `superadmin`). Подробнее о ролях: [docs/ADMIN_PANEL.md](docs/ADMIN_PANEL.md).

---
© 2026 UstaGo — Профессиональная платформа для рынка услуг.
