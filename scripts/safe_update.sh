#!/bin/bash
# =================================================================
# 🛡️ UstaGo — безопасное последовательное обновление сервера
#
#   0. проверки перед началом (диск, база, .env, сервисы)
#   1. снимок «до»: коммит, версия миграций, число пользователей, дамп базы (с проверкой)
#   2. показ того, что будет обновлено, и подтверждение
#   3. само обновление (scripts/update.sh: код → зависимости → миграции → сборка → перезапуск)
#   4. проверка «после»: миграции на последней версии, пользователей не меньше, сервисы живы, API отвечает
#
# Запуск:   bash scripts/safe_update.sh            (с вопросом перед обновлением)
#           bash scripts/safe_update.sh --yes      (без вопроса)
#           bash scripts/safe_update.sh --check    (только проверки и список изменений, ничего не меняет)
#           bash scripts/safe_update.sh --force    (обновлять, даже если новых коммитов нет: пересборка и перезапуск)
# Если что-то пошло не так:  bash scripts/rollback.sh
# =================================================================
set -Eeuo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
say()  { echo -e "${BLUE}▶ $*${NC}"; }
ok()   { echo -e "${GREEN}✔ $*${NC}"; }
has_unit() { local u; u="$(systemctl list-unit-files 2>/dev/null || true)"; grep -q "^$1" <<<"$u"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
die()  { echo -e "${RED}✖ $*${NC}" >&2; exit 1; }

ASSUME_YES=0; CHECK_ONLY=0; FORCE=0
for a in "$@"; do
  case "$a" in
    -y|--yes) ASSUME_YES=1 ;;
    --check)  CHECK_ONLY=1 ;;
    --force)  FORCE=1 ;;
    -h|--help) sed -n 2,20p "$0"; exit 0 ;;
    *) die "Неизвестный параметр: $a" ;;
  esac
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."
export PATH="$HOME/.local/bin:$PATH"
BRANCH="${UPDATE_BRANCH:-main}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/ustago_backups}"
STATE_FILE="$BACKUP_DIR/last_update.env"
TS="$(date +%F_%H%M%S)"
STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
mkdir -p "$BACKUP_DIR"

PHASE="проверки"
UPDATE_STARTED=0
on_error() {
  echo -e "\n${RED}✖ Остановлено на этапе: ${PHASE}.${NC}" >&2
  if [ "$UPDATE_STARTED" = 1 ]; then
    echo -e "${YELLOW}Обновление уже начиналось. Состояние до него сохранено: ${STATE_FILE}" >&2
    echo -e "Откатить код:           bash scripts/rollback.sh" >&2
    echo -e "Откатить код и базу:    bash scripts/rollback.sh --with-db   (данные, появившиеся после дампа, будут потеряны)${NC}" >&2
  else
    echo -e "${GREEN}Ничего не изменено, можно спокойно исправить причину и запустить снова.${NC}" >&2
  fi
}
trap on_error ERR

# ---------- доступ к базе (параметры берём из .env) ----------
[ -f .env ] || die "Нет файла .env в $(pwd)"
eval "$(python3 - <<'PY'
import os, shlex
from urllib.parse import urlparse, parse_qs, unquote
env = {}
for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
url = env.get("DATABASE_URL", "")
name = user = pw = host = port = ""
if url:
    u = urlparse(url)
    name = (u.path or "").lstrip("/")
    user, pw = unquote(u.username or ""), unquote(u.password or "")
    host, port = u.hostname or "", str(u.port or "")
    q = parse_qs(u.query)
    if not host and q.get("host"):
        host = q["host"][0]
else:
    name, user, pw = env.get("DB_NAME", ""), env.get("DB_USER", ""), env.get("DB_PASS", "")
    host, port = env.get("DB_HOST", ""), env.get("DB_PORT", "")
for k, v in (("DB_NAME", name), ("DB_USER", user), ("DB_PASS", pw), ("DB_HOST", host), ("DB_PORT", port)):
    print(f"{k}={shlex.quote(v)}")
PY
)"
[ -n "$DB_NAME" ] || die "Не удалось определить имя базы из .env (DATABASE_URL или DB_NAME)"

# pg <команда> <аргументы>: локальная база — от имени postgres, иначе по логину из .env
pg() {
  local cmd="$1"; shift
  if { [ -z "$DB_HOST" ] || [ "$DB_HOST" = localhost ] || [ "$DB_HOST" = 127.0.0.1 ]; } \
     && [ -z "${PG_FORCE_TCP:-}" ] && sudo -n -u postgres true 2>/dev/null; then
    sudo -n -u postgres "$cmd" "$@"
  else
    PGPASSWORD="$DB_PASS" "$cmd" ${DB_HOST:+-h "$DB_HOST"} ${DB_PORT:+-p "$DB_PORT"} ${DB_USER:+-U "$DB_USER"} "$@"
  fi
}
count_users() { pg psql -d "$DB_NAME" -tAc "select count(*) from users" | tr -d '[:space:]'; }
alembic_current() { uv run --frozen alembic current 2>&1 | grep -E '^[0-9a-f]{6,}' | tail -1 || true; }

# ---------- 0. проверки ----------
PHASE="проверки перед обновлением"
say "0. Проверки перед обновлением"
command -v git >/dev/null || die "git не найден"
command -v uv  >/dev/null || die "uv не найден (curl -LsSf https://astral.sh/uv/install.sh | sh)"
command -v python3 >/dev/null || die "python3 не найден"
FREE_MB=$(df -Pm . | awk 'NR==2{print $4}')
[ "$FREE_MB" -ge 1024 ] || die "Мало места на диске: свободно ${FREE_MB} МБ, нужно хотя бы 1024"
ok "Свободно на диске: ${FREE_MB} МБ"
USERS_BEFORE="$(count_users)" || die "Не удалось подключиться к базе $DB_NAME"
ok "База $DB_NAME доступна, пользователей: $USERS_BEFORE"
OLD_REV="$(alembic_current)"; ok "Версия миграций сейчас: ${OLD_REV:-неизвестна}"
OLD_COMMIT="$(git rev-parse HEAD)"; ok "Текущий коммит: $(git --no-pager log --oneline -1)"
if command -v redis-cli >/dev/null && [ "$(redis-cli ping 2>/dev/null || true)" = PONG ]; then ok "Redis отвечает"
else warn "Redis недоступен: бот и вход в админку будут работать в упрощённом режиме (состояния сбрасываются при перезапуске)"; fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  warn "В рабочей папке есть незакоммиченные изменения (update.sh сохранит их через stash и вернёт):"
  git --no-pager status --short --untracked-files=no | sed 's/^/    /'
fi

say "Что будет обновлено"
git fetch origin "$BRANCH" --quiet || die "Не удалось получить $BRANCH из GitHub (нет сети или доступа)"
PENDING="$(git --no-pager log --oneline "HEAD..FETCH_HEAD")"
if [ -n "$PENDING" ]; then
  echo "$PENDING" | sed 's/^/    /'
  git --no-pager diff --stat HEAD FETCH_HEAD | tail -1 | sed 's/^/    /'
  NEW_MIGRATIONS="$(git diff --name-only --diff-filter=A HEAD FETCH_HEAD -- alembic/versions | wc -l | tr -d ' ')"
  if [ "$NEW_MIGRATIONS" -gt 0 ]; then warn "Новых миграций базы: $NEW_MIGRATIONS (они только добавляют таблицы/колонки/индексы)"; fi
else
  echo "    новых коммитов на GitHub нет"
  # код мог быть подтянут вручную (git pull), а база и сервисы остаться на старой версии
  if ! grep -q "(head)" <<<"${OLD_REV:-}"; then
    warn "Но в базе есть непримененные миграции (версия: ${OLD_REV:-неизвестна}) — обновление нужно довести до конца"
  elif [ "$FORCE" != 1 ]; then
    ok "Код и база уже актуальны, обновлять нечего. (Пересобрать и перезапустить всё равно: bash scripts/safe_update.sh --force)"
    exit 0
  fi
fi
if [ "$CHECK_ONLY" = 1 ]; then ok "Режим --check: ничего не изменено."; exit 0; fi

# ---------- 1. снимок «до» ----------
PHASE="резервная копия"
say "1. Резервная копия базы"
DUMP="$BACKUP_DIR/ustago_before_update_${TS}.dump"
pg pg_dump -Fc "$DB_NAME" > "$DUMP"
[ -s "$DUMP" ] || die "Дамп пустой: $DUMP"
pg_restore --list "$DUMP" > /dev/null || die "Дамп не читается: $DUMP"
TABLES="$(pg_restore --list "$DUMP" | grep -c 'TABLE DATA' || true)"
ok "Дамп создан и проверен: $DUMP ($(du -h "$DUMP" | cut -f1), таблиц с данными: $TABLES)"
{
  printf 'OLD_COMMIT=%q\n' "$OLD_COMMIT"
  printf 'OLD_REV=%q\n' "${OLD_REV:-}"
  printf 'DUMP=%q\n' "$DUMP"
  printf 'USERS_BEFORE=%q\n' "$USERS_BEFORE"
  printf 'STARTED_AT=%q\n' "$STARTED_AT"
} > "$STATE_FILE"
ok "Состояние «до» записано: $STATE_FILE"
# хранить только 10 последних дампов
ls -1t "$BACKUP_DIR"/ustago_before_update_*.dump 2>/dev/null | tail -n +11 | xargs -r rm -f --

# ---------- 2. подтверждение ----------
if [ "$ASSUME_YES" != 1 ]; then
  echo
  read -r -p "Начать обновление? Сервисы будут перезапущены на 10–30 секунд. [y/N] " ans
  case "$ans" in y|Y|yes|да|д) ;; *) echo "Отменено. Ничего не изменено (дамп сохранён: $DUMP)."; exit 0 ;; esac
fi

# ---------- 3. обновление ----------
PHASE="обновление (scripts/update.sh)"
UPDATE_STARTED=1
say "3. Обновление"
LOG="$BACKUP_DIR/update_${TS}.log"
bash scripts/update.sh 2>&1 | tee "$LOG"
ok "update.sh завершился, лог: $LOG"

# ---------- 4. проверка «после» ----------
PHASE="проверка после обновления"
say "4. Проверка после обновления"
FAILS=0
check() { # check "описание" команда...
  local what="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$what"; else echo -e "${RED}✖ $what${NC}"; FAILS=$((FAILS+1)); fi
}
retry() { local n="$1"; shift; local i; for ((i=0;i<n;i++)); do "$@" && return 0; sleep 2; done; return 1; }

NEW_REV="$(alembic_current)"
if echo "$NEW_REV" | grep -q "(head)"; then ok "Миграции на последней версии: $NEW_REV"
else echo -e "${RED}✖ Версия миграций не последняя: ${NEW_REV:-неизвестна}${NC}"; FAILS=$((FAILS+1)); fi

USERS_AFTER="$(count_users)"
if [ "$USERS_AFTER" -ge "$USERS_BEFORE" ]; then ok "Пользователей: было $USERS_BEFORE, стало $USERS_AFTER"
else echo -e "${RED}✖ Пользователей стало меньше: было $USERS_BEFORE, стало $USERS_AFTER${NC}"; FAILS=$((FAILS+1)); fi

if command -v pm2 >/dev/null; then
  pm2_online() { pm2 jlist 2>/dev/null | python3 -c "
import json,sys
names={p['name']:p['pm2_env']['status'] for p in json.load(sys.stdin)}
sys.exit(0 if all(names.get(n)=='online' for n in ('ustago-backend','ustago-frontend')) else 1)"; }
  check "PM2: ustago-backend и ustago-frontend работают" retry 10 pm2_online
fi
if has_unit ustago.service; then
  check "Бот (systemd ustago) активен" retry 10 systemctl is-active --quiet ustago
fi
if command -v curl >/dev/null; then
  check "API отвечает (http://127.0.0.1:8000/api/v1/health)" retry 15 curl -fsS -o /dev/null http://127.0.0.1:8000/api/v1/health
  check "Панель отвечает (http://127.0.0.1:3000)" retry 15 curl -fsS -o /dev/null http://127.0.0.1:3000/login
fi
if command -v journalctl >/dev/null && has_unit ustago.service; then
  sleep 3
  TB="$(journalctl -u ustago --since "$STARTED_AT" --no-pager 2>/dev/null | grep -c 'Traceback' || true)"
  if [ "${TB:-0}" -eq 0 ]; then ok "В логе бота после обновления нет Traceback"
  else echo -e "${RED}✖ В логе бота есть Traceback (${TB}): journalctl -u ustago --since \"$STARTED_AT\"${NC}"; FAILS=$((FAILS+1)); fi
  if journalctl -u ustago --since "$STARTED_AT" --no-pager 2>/dev/null | grep -q 'falling back to MemoryStorage'; then
    warn "Бот работает без Redis (диалоги пользователей сбросятся при следующем перезапуске)"; fi
fi

echo
if [ "$FAILS" -eq 0 ]; then
  echo -e "${GREEN}==============================================${NC}"
  echo -e "${GREEN}✅ ОБНОВЛЕНИЕ ПРОШЛО УСПЕШНО, ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ${NC}"
  echo -e "${GREEN}==============================================${NC}"
  echo "Дамп «до» (на всякий случай): $DUMP"
  echo "Скопируйте его на свой компьютер:  scp root@<сервер>:$DUMP ."
else
  trap - ERR
  echo -e "${RED}==============================================${NC}"
  echo -e "${RED}✖ ПРОВЕРОК НЕ ПРОЙДЕНО: $FAILS${NC}"
  echo -e "${RED}==============================================${NC}"
  echo "Посмотрите логи: pm2 logs ustago-backend --lines 50 --nostream ; journalctl -u ustago -n 50 --no-pager"
  echo "Откат кода:          bash scripts/rollback.sh"
  echo "Откат кода и базы:   bash scripts/rollback.sh --with-db   (данные после дампа будут потеряны)"
  exit 1
fi
