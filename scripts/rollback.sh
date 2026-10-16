#!/bin/bash
# =================================================================
# ↩️  UstaGo — откат после неудачного обновления
#
# Использует состояние, которое записал scripts/safe_update.sh
# (~/ustago_backups/last_update.env: коммит «до» и дамп базы «до»).
#
#   bash scripts/rollback.sh               откатить только КОД (база остаётся как есть, данные не теряются)
#   bash scripts/rollback.sh --with-db     откатить код И базу из дампа
#                                          (всё, что появилось после дампа — новые пользователи, заявки, баллы — будет потеряно!)
#   bash scripts/rollback.sh --commit <хеш> [--dump <файл>]   указать коммит/дамп вручную
#   bash scripts/rollback.sh --yes         без вопроса
#
# Откат только кода безопасен, пока миграции лишь добавляют таблицы и колонки: старый код их просто не использует.
# =================================================================
set -Eeuo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
say()  { echo -e "${BLUE}▶ $*${NC}"; }
ok()   { echo -e "${GREEN}✔ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
die()  { echo -e "${RED}✖ $*${NC}" >&2; exit 1; }
has_unit() { local u; u="$(systemctl list-unit-files 2>/dev/null || true)"; grep -q "^$1" <<<"$u"; }

WITH_DB=0; ASSUME_YES=0; COMMIT=""; DUMP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --with-db) WITH_DB=1 ;;
    -y|--yes)  ASSUME_YES=1 ;;
    --commit)  COMMIT="${2:-}"; shift ;;
    --dump)    DUMP="${2:-}"; shift ;;
    -h|--help) sed -n 2,16p "$0"; exit 0 ;;
    *) die "Неизвестный параметр: $1" ;;
  esac
  shift
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."
export PATH="$HOME/.local/bin:$PATH"
BACKUP_DIR="${BACKUP_DIR:-$HOME/ustago_backups}"
STATE_FILE="$BACKUP_DIR/last_update.env"

CLI_COMMIT="$COMMIT"; CLI_DUMP="$DUMP"
if [ -f "$STATE_FILE" ]; then
  # shellcheck disable=SC1090
  . "$STATE_FILE"     # задаёт OLD_COMMIT и DUMP (то, что записал safe_update.sh)
fi
COMMIT="${CLI_COMMIT:-${OLD_COMMIT:-}}"; DUMP="${CLI_DUMP:-${DUMP:-}}"
[ -n "$COMMIT" ] || die "Не знаю, на какой коммит откатываться. Укажите: --commit <хеш>"
git cat-file -e "$COMMIT^{commit}" 2>/dev/null || die "Коммит $COMMIT не найден в этой папке"
if [ "$WITH_DB" = 1 ]; then
  [ -n "$DUMP" ] && [ -s "$DUMP" ] || die "Дамп не найден (${DUMP:-не указан}). Укажите: --dump <файл>"
  pg_restore --list "$DUMP" >/dev/null || die "Дамп не читается: $DUMP"
fi

[ -f .env ] || die "Нет файла .env в $(pwd)"
eval "$(python3 - <<'PY'
import shlex
from urllib.parse import urlparse, parse_qs, unquote
env = {}
for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
url = env.get("DATABASE_URL", "")
if url:
    u = urlparse(url); q = parse_qs(u.query)
    name, user, pw = (u.path or "").lstrip("/"), unquote(u.username or ""), unquote(u.password or "")
    host, port = u.hostname or (q.get("host", [""])[0]), str(u.port or "")
else:
    name, user, pw = env.get("DB_NAME", ""), env.get("DB_USER", ""), env.get("DB_PASS", "")
    host, port = env.get("DB_HOST", ""), env.get("DB_PORT", "")
for k, v in (("DB_NAME", name), ("DB_USER", user), ("DB_PASS", pw), ("DB_HOST", host), ("DB_PORT", port)):
    print(f"{k}={shlex.quote(v)}")
PY
)"
pg() {
  local cmd="$1"; shift
  if { [ -z "$DB_HOST" ] || [ "$DB_HOST" = localhost ] || [ "$DB_HOST" = 127.0.0.1 ]; } \
     && [ -z "${PG_FORCE_TCP:-}" ] && sudo -n -u postgres true 2>/dev/null; then
    sudo -n -u postgres "$cmd" "$@"
  else
    PGPASSWORD="$DB_PASS" "$cmd" ${DB_HOST:+-h "$DB_HOST"} ${DB_PORT:+-p "$DB_PORT"} ${DB_USER:+-U "$DB_USER"} "$@"
  fi
}

echo -e "${YELLOW}Откат:${NC}"
echo "  код      → $(git --no-pager log --oneline -1 "$COMMIT")"
if [ "$WITH_DB" = 1 ]; then
  echo -e "  ${RED}база     → из дампа $DUMP (ВСЁ, что появилось после дампа, будет потеряно)${NC}"
else
  echo "  база     → не трогаем"
fi
if [ "$ASSUME_YES" != 1 ]; then
  [ "$WITH_DB" = 1 ] && PHRASE="ОТКАТ С БАЗОЙ" || PHRASE="ОТКАТ"
  read -r -p "Для подтверждения введите «$PHRASE»: " ans
  [ "$ans" = "$PHRASE" ] || { echo "Отменено, ничего не изменено."; exit 0; }
fi

say "1. Остановка сервисов"
has_unit ustago.service && sudo systemctl stop ustago || true
command -v pm2 >/dev/null && { pm2 stop ustago-backend ustago-frontend >/dev/null 2>&1 || true; }

if [ "$WITH_DB" = 1 ]; then
  say "2. Восстановление базы из дампа"
  pg pg_restore --clean --if-exists -d "$DB_NAME" < "$DUMP" || warn "pg_restore сообщил о предупреждениях (обычно безвредно, проверьте число пользователей ниже)"
  ok "База восстановлена"
fi

say "3. Возврат кода"
git stash save "Autostash before rollback" --quiet || true
git reset --hard "$COMMIT"
ok "Код: $(git --no-pager log --oneline -1)"

say "4. Зависимости и сборка панели"
uv sync
( cd admin_frontend && npm install --no-audit --no-fund && npm run build )

say "5. Запуск сервисов"
if command -v pm2 >/dev/null; then
  pm2 restart ustago-backend 2>/dev/null || pm2 start "uv run uvicorn admin_api.main:app --host 0.0.0.0 --port 8000" --name ustago-backend
  pm2 restart ustago-frontend 2>/dev/null || pm2 start "npm run start" --name ustago-frontend --cwd "$(pwd)/admin_frontend"
  pm2 save >/dev/null
fi
has_unit ustago.service && sudo systemctl start ustago || true

say "6. Проверка"
sleep 5
USERS="$(pg psql -d "$DB_NAME" -tAc 'select count(*) from users' | tr -d '[:space:]' || true)"
ok "Пользователей в базе: ${USERS:-?}"
command -v curl >/dev/null && { curl -fsS -o /dev/null http://127.0.0.1:8000/api/v1/health && ok "API отвечает" || warn "API пока не отвечает: pm2 logs ustago-backend --lines 50 --nostream"; }
has_unit ustago.service && { systemctl is-active --quiet ustago && ok "Бот активен" || warn "Бот не активен: journalctl -u ustago -n 50 --no-pager"; }
echo -e "${GREEN}Откат завершён.${NC}"
[ "$WITH_DB" = 1 ] || warn "База осталась на новой схеме. Если нужно вернуть и её: bash scripts/rollback.sh --with-db"
