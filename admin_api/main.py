from fastapi import FastAPI, Depends, HTTPException, Body, Request
from admin_api import security
from admin_api.security import ROLE_SUPER, ROLE_MODERATOR, ROLE_FINANCE, ADMIN_ROLES, effective_role
from sqlalchemy import select, func, update, or_, exists
from sqlalchemy.orm import selectinload
from database.engine import async_session_maker
from database.models import User, MasterProfile, Order, OrderStatus, UserRole, MasterStatus, Category, District, Transaction, TransactionType, TopUpRequest, Bid, SystemSettings, AdminLog
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from bot.core.config import config
from aiogram import Bot
from fastapi.responses import FileResponse, StreamingResponse
from bot.services import orders as order_service
import csv
import io
from statistics import median
import admin_api.backups as backup_util
from bot.services import billing
import asyncio
import sentry_sdk
import random
import secrets
import hmac
import logging
import time
from database.models import BidStatus

# --- SENTRY INITIALIZATION ---
if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=0.3,
        profiles_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
        enable_tracing=True,
    )

app = FastAPI(title="UstaGo Admin API")
bot_instance = Bot(token=config.BOT_TOKEN)

async def notify_user(telegram_id: int, message: str):
    """Sends a notification to the user via Telegram bot."""
    try:
        await bot_instance.send_message(telegram_id, message, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to notify user {telegram_id}: {e}")

async def log_action(session, action: str, details: str, admin_id: Optional[int] = None):
    """Utility to log administrative actions."""
    session.add(AdminLog(action=action, details=details, admin_id=admin_id))

_cors_origins = config.CORS_ORIGINS or ["*"]
if _cors_origins == ["*"]:
    logging.getLogger("admin_api").warning(
        "CORS_ORIGINS is not set: allowing all origins. Set CORS_ORIGINS in .env for production."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,  # auth is a Bearer header, cookies are not used
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Start background task for daily backups
    asyncio.create_task(scheduled_backups())

async def scheduled_backups():
    """Background task to create a backup every 24 hours."""
    # Wait 1 minute after startup before first backup
    await asyncio.sleep(60)
    
    while True:
        try:
            print(f"[{datetime.now()}] Starting automated backup...")
            await backup_util.create_backup()
            # Clean old backups (keep last 10)
            backups = backup_util.list_backups()
            if len(backups) > 10:
                for b in backups[10:]:
                    backup_util.delete_backup(b["filename"])
        except Exception as e:
            print(f"Scheduled backup failed: {e}")
        
        await asyncio.sleep(60 * 60 * 24) # 24 hours

# Security Configuration
SECRET_KEY = config.JWT_SECRET_KEY
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set or shorter than 32 chars. Generate one: "
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\" and put it into .env"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# --- AUTH UTILS ---

_DUMMY_HASH = pwd_context.hash(secrets.token_urlsafe(8))

def verify_password(plain_password, hashed_password):
    if not hashed_password: return False
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    async with async_session_maker() as session:
        stmt = select(User).where(User.username == username)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise credentials_exception
        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user

def require_role(*allowed: str):
    """Dependency factory: SUPERADMIN always passes, the listed roles pass, everyone else gets 403 (empty list = superadmin only)."""
    async def checker(current_user: User = Depends(get_current_user)):
        role = effective_role(current_user)
        if role != ROLE_SUPER and role not in allowed:
            raise HTTPException(status_code=403, detail="Недостаточно прав для этого действия")
        return current_user
    return checker


MODERATION = require_role(ROLE_MODERATOR)   # masters, order cancellation
FINANCE = require_role(ROLE_FINANCE)        # points, top-ups
SUPERADMIN = require_role()                 # settings, directories, logs, backups, admins

# --- AUTH ENDPOINTS ---

@app.post("/api/v1/auth/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    ip = security.client_ip(request)
    await security.ensure_login_allowed(form_data.username, ip)

    async with async_session_maker() as session:
        stmt = select(User).where(User.username == form_data.username)
        user = (await session.execute(stmt)).scalar_one_or_none()

        # bcrypt always runs (dummy hash for unknown users) so response time does not reveal which usernames exist
        is_valid = verify_password(form_data.password, user.hashed_password if user else _DUMMY_HASH) and bool(user)
        if not is_valid:
            await security.register_login_failure(form_data.username, ip)
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Not enough permissions")

        # Generate 2FA code and send to Telegram
        code = str(secrets.randbelow(900000) + 100000)
        await security.save_2fa_code(user.username, code)

        try:
            await bot_instance.send_message(
                user.telegram_id,
                f"🔐 <b>Код подтверждения для входа в админ-панель:</b>\n\n"
                f"<code>{code}</code>\n\n"
                f"⏱ Код действителен 5 минут.\n"
                f"❗️ Если вы не запрашивали вход, проигнорируйте это сообщение.",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.getLogger("admin_api").error("Failed to send 2FA code to %s: %s", user.telegram_id, e)
            raise HTTPException(status_code=500, detail="Failed to send 2FA code")

        return {"requires_2fa": True, "message": "2FA code sent to your Telegram"}

class TwoFAVerify(BaseModel):
    username: str
    code: str

@app.post("/api/v1/auth/verify-2fa")
async def verify_2fa(data: TwoFAVerify, request: Request):
    ip = security.client_ip(request)
    await security.ensure_login_allowed(data.username, ip)

    result = await security.check_2fa_code(data.username, data.code)
    if result == "missing":
        raise HTTPException(status_code=400, detail="No 2FA code requested or it expired. Please login again.")
    if result in ("wrong", "locked"):
        await security.register_login_failure(data.username, ip)
        if result == "locked":
            raise HTTPException(status_code=400, detail="Too many invalid codes. Please login again.")
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    await security.clear_login_failures(data.username, ip)
    access_token = create_access_token(
        data={"sub": data.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v1/auth/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "admin_role": effective_role(current_user),
    }

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

@app.post("/api/v1/auth/change-password")
async def change_password(data: PasswordChange, current_user: User = Depends(get_current_user)):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Incorrect old password"
        )
    
    async with async_session_maker() as session:
        stmt = update(User).where(User.id == current_user.id).values(
            hashed_password=get_password_hash(data.new_password)
        )
        await session.execute(stmt)
        await session.commit()
        return {"status": "success", "message": "Password changed successfully"}

# Редирект старой зависимости для совместимости на время перехода (постепенно заменим)
async def verify_api_key(current_user: User = Depends(get_current_user)):
    return current_user

EXPORT_LIMIT = 20000
INT32_MAX = 2**31 - 1
INT64_MAX = 2**63 - 1


def _enum(v):
    return getattr(v, "value", v)


def _safe_cell(v):
    """Neutralises spreadsheet formula injection (=, +, -, @) in user-controlled text."""
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _csv_response(filename: str, header: list, rows: list) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM so Excel opens UTF-8 correctly
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    for r in rows:
        w.writerow([_safe_cell(c) for c in r])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


class AdminRoleUpdate(BaseModel):
    admin_role: str


@app.get("/api/v1/admins", dependencies=[Depends(SUPERADMIN)])
async def list_admins():
    async with async_session_maker() as session:
        admins = (await session.execute(select(User).where(User.role == UserRole.ADMIN).order_by(User.id))).scalars().all()
        return [{"id": a.id, "username": a.username, "full_name": a.full_name, "telegram_id": a.telegram_id,
                 "admin_role": effective_role(a), "has_password": bool(a.hashed_password)} for a in admins]


@app.patch("/api/v1/admins/{user_id}", dependencies=[Depends(SUPERADMIN)])
async def set_admin_role(user_id: int, data: AdminRoleUpdate, current_user: User = Depends(get_current_user)):
    if data.admin_role not in ADMIN_ROLES:
        raise HTTPException(status_code=400, detail=f"Роль должна быть одной из: {', '.join(ADMIN_ROLES)}")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя менять собственную роль")
    async with async_session_maker() as session:
        target = (await session.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one_or_none()
        if not target or target.role != UserRole.ADMIN:
            raise HTTPException(status_code=404, detail="Администратор не найден")
        old = effective_role(target)
        target.admin_role = data.admin_role
        await log_action(session, "SET_ADMIN_ROLE", f"Admin #{target.id} ({target.username}): {old} -> {data.admin_role}",
                         admin_id=current_user.id)
        await session.commit()
    return {"status": "success", "admin_role": data.admin_role}


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/v1/stats", dependencies=[Depends(verify_api_key)])
async def get_mini_stats():
    """Returns main metrics for the dashboard home page."""
    async with async_session_maker() as session:
        # Total users
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        
        # Masters stats
        total_masters = (await session.execute(select(func.count(MasterProfile.id)))).scalar() or 0
        pending_masters = (await session.execute(
            select(func.count(MasterProfile.id)).where(MasterProfile.status == MasterStatus.PENDING)
        )).scalar() or 0
        
        # Clients
        total_clients = (await session.execute(
            select(func.count(User.id)).where(User.role == UserRole.CLIENT)
        )).scalar() or 0
        
        # Orders stats
        active_orders = (await session.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.ACTIVE)
        )).scalar() or 0
        new_orders = (await session.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.NEW)
        )).scalar() or 0
        
        return {
            "users": {
                "total": total_users,
                "clients": total_clients,
                "masters": total_masters
            },
            "moderation": {
                "pending_masters": pending_masters
            },
            "orders": {
                "active": active_orders,
                "new": new_orders,
                "completed": (await session.execute(
                    select(func.count(Order.id)).where(Order.status == OrderStatus.COMPLETED)
                )).scalar() or 0
            },
            "finance": {
                "total_points_in_system": (await session.execute(select(func.sum(User.points)))).scalar() or 0,
                "total_deposits": (await session.execute(
                    select(func.sum(TopUpRequest.amount)).where(TopUpRequest.status == "APPROVED")
                )).scalar() or 0,
                "total_revenue": (await session.execute(
                    select(func.abs(func.sum(Transaction.amount)))
                    .where(Transaction.type == TransactionType.CONTACT_FEE)
                )).scalar() or 0
            },
            "categories_breakdown": [
                {"name": name, "count": count}
                for name, count in (await session.execute(
                    select(Category.name, func.count(Order.id))
                    .join(Order, Order.category_id == Category.id)
                    .group_by(Category.name)
                    .order_by(func.count(Order.id).desc())
                )).all()
            ],
            "districts_breakdown": [
                {"name": name, "count": count}
                for name, count in (await session.execute(
                    select(District.name, func.count(Order.id))
                    .join(Order, Order.district_id == District.id)
                    .group_by(District.name)
                    .order_by(func.count(Order.id).desc())
                    .limit(5)
                )).all()
            ],
            "order_status_distribution": [
                {"name": status.value, "value": count}
                for status, count in (await session.execute(
                    select(Order.status, func.count(Order.id))
                    .group_by(Order.status)
                )).all()
            ]
        }

@app.get("/api/v1/stats/funnel", dependencies=[Depends(verify_api_key)])
async def get_funnel(days: int = 30):
    """Conversion funnel for orders created in the last `days` days."""
    days = max(1, min(days, 365))
    cutoff = datetime.utcnow() - timedelta(days=days)
    async with async_session_maker() as session:
        orders = (await session.execute(
            select(Order.id, Order.status, Order.created_at).where(Order.created_at >= cutoff)
        )).all()
        first_bid = dict((await session.execute(
            select(Bid.order_id, func.min(Bid.created_at)).join(Order, Order.id == Bid.order_id)
            .where(Order.created_at >= cutoff).group_by(Bid.order_id)
        )).all())
        active_masters = (await session.execute(
            select(func.count(func.distinct(Bid.master_id))).where(Bid.created_at >= cutoff)
        )).scalar() or 0

    created = len(orders)
    with_bids = sum(1 for o in orders if o.id in first_bid)
    accepted = sum(1 for o in orders if o.status in (OrderStatus.ACTIVE, OrderStatus.COMPLETED))
    completed = sum(1 for o in orders if o.status == OrderStatus.COMPLETED)
    cancelled = sum(1 for o in orders if o.status == OrderStatus.CANCELLED)
    waits = [(first_bid[o.id] - o.created_at).total_seconds() / 60 for o in orders if o.id in first_bid]

    def pct(a, b):
        return round(a * 100 / b, 1) if b else 0.0

    return {
        "days": days,
        "created": created, "with_bids": with_bids, "accepted": accepted, "completed": completed, "cancelled": cancelled,
        "bid_rate": pct(with_bids, created), "accept_rate": pct(accepted, with_bids),
        "completion_rate": pct(completed, accepted), "no_response": max(0, created - with_bids - cancelled),
        "median_first_bid_minutes": round(median(waits), 1) if waits else None,
        "active_masters": active_masters,
    }


@app.get("/api/v1/stats/orders-chart", dependencies=[Depends(verify_api_key)])
async def get_orders_chart_data(
    days: Optional[int] = 7, 
    start: Optional[str] = None, 
    end: Optional[str] = None,
    master_id: Optional[int] = None,
    category_id: Optional[int] = None,
    district_id: Optional[int] = None,
    split_by: Optional[str] = None # None, 'category', 'district', 'master'
):
    """Returns order counts grouped by day, optionally split by category/district/master."""
    async with async_session_maker() as session:
        try:
            if start and end:
                start_dt = datetime.fromisoformat(start)
                end_dt = datetime.fromisoformat(end)
            else:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=days)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

        # Base filter
        where_clause = [Order.created_at >= start_dt, Order.created_at <= end_dt]
        if category_id: where_clause.append(Order.category_id == category_id)
        if district_id: where_clause.append(Order.district_id == district_id)
        
        if split_by == 'category':
            stmt = select(func.date(Order.created_at).label("day"), Category.name.label("label"), func.count(Order.id))\
                .join(Category, Order.category_id == Category.id)\
                .where(*where_clause)\
                .group_by(func.date(Order.created_at), Category.name)
        elif split_by == 'district':
            stmt = select(func.date(Order.created_at).label("day"), District.name.label("label"), func.count(Order.id))\
                .join(District, Order.district_id == District.id)\
                .where(*where_clause)\
                .group_by(func.date(Order.created_at), District.name)
        elif split_by == 'master':
            stmt = select(func.date(Order.created_at).label("day"), User.full_name.label("label"), func.count(Order.id))\
                .join(Bid, Bid.order_id == Order.id)\
                .join(MasterProfile, Bid.master_id == MasterProfile.id)\
                .join(User, MasterProfile.user_id == User.id)\
                .where(*where_clause, Bid.status == BidStatus.ACCEPTED)\
                .group_by(func.date(Order.created_at), User.full_name)
        else:
            # Default: split by 'Total' or apply master_id filter
            stmt = select(func.date(Order.created_at).label("day"), func.count(Order.id))
            if master_id:
                stmt = stmt.join(Bid).where(Bid.master_id == master_id, Bid.status == BidStatus.ACCEPTED)
            stmt = stmt.where(*where_clause).group_by(func.date(Order.created_at))

        results = (await session.execute(stmt)).all()
        
        # Structure the data for Recharts [ {date: '...', Label1: N, Label2: M}, ... ]
        data_map = {} # date -> { label -> count }
        all_labels = set()
        
        for r in results:
            day_str = str(r[0])
            if split_by in ['category', 'district', 'master']:
                label = r[1]
                count = r[2]
                if day_str not in data_map: data_map[day_str] = {}
                data_map[day_str][label] = count
                all_labels.add(label)
            else:
                count = r[1]
                data_map[day_str] = {"Всего": count}
                all_labels.add("Всего")

        delta = (end_dt.date() - start_dt.date()).days
        chart_data = []
        for i in range(delta + 1):
            day = (start_dt.date() + timedelta(days=i))
            day_str = str(day)
            
            entry = {
                "date": day.strftime("%d.%m"),
                "full_date": day_str,
            }
            # Fill all labels (ensure zeros)
            day_values = data_map.get(day_str, {})
            for lbl in all_labels:
                entry[lbl] = day_values.get(lbl, 0)
                
            chart_data.append(entry)
            
        return chart_data

# --- SCHEMAS ---
class MasterUpdate(BaseModel):
    status: Optional[MasterStatus] = None
    is_accredited: Optional[bool] = None

class PointAdjustment(BaseModel):
    amount: int
    description: str

class NameUpdate(BaseModel):
    name: str

class TopUpReview(BaseModel):
    status: str # APPROVED or REJECTED

class SystemSettingsUpdate(BaseModel):
    crypto_enabled: Optional[bool] = None
    crypto_address: Optional[str] = None
    bank_enabled: Optional[bool] = None
    bank_details: Optional[str] = None
    free_orders_enabled: Optional[bool] = None

class BulkPointAdjustment(BaseModel):
    master_ids: Optional[List[int]] = None
    all_masters: bool = False
    amount: int
    description: str

# --- ENDPOINTS ---

@app.get("/api/v1/settings", dependencies=[Depends(verify_api_key)])
async def get_settings():
    async with async_session_maker() as session:
        settings = (await session.execute(select(SystemSettings))).scalar_one_or_none()
        if not settings:
            settings = SystemSettings()
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings

@app.patch("/api/v1/settings", dependencies=[Depends(SUPERADMIN)])
async def update_settings(data: SystemSettingsUpdate, current_user: User = Depends(get_current_user)):
    async with async_session_maker() as session:
        settings = (await session.execute(select(SystemSettings))).scalar_one_or_none()
        if not settings:
            settings = SystemSettings()
            session.add(settings)
            
        if data.crypto_enabled is not None: settings.crypto_enabled = data.crypto_enabled
        if data.crypto_address is not None: settings.crypto_address = data.crypto_address
        if data.bank_enabled is not None: settings.bank_enabled = data.bank_enabled
        if data.bank_details is not None: settings.bank_details = data.bank_details
        if data.free_orders_enabled is not None: settings.free_orders_enabled = data.free_orders_enabled
        
        await log_action(session, "UPDATE_SETTINGS", f"Settings updated: {data.model_dump_json(exclude_none=True)}", admin_id=current_user.id)
        await session.commit()
        return {"status": "success"}

def _user_filters(role, q, master_status):
    """WHERE-clauses shared by the users list and the CSV export."""
    conds = []
    if role:
        conds.append(User.role == role)
    if q and q.strip():
        term = q.strip().lstrip("@")
        like = f"%{term}%"
        parts = [User.full_name.ilike(like), User.username.ilike(like), User.phone_number.ilike(like)]
        if term.isdigit():
            n = int(term)
            if n <= INT32_MAX:
                parts.append(User.id == n)
            if n <= INT64_MAX:
                parts.append(User.telegram_id == n)
        conds.append(or_(*parts))
    if master_status:
        conds.append(exists().where(MasterProfile.user_id == User.id, MasterProfile.status == master_status))
    return conds


def _user_row(u: User) -> dict:
    master_data = None
    if u.master_profile:
        bids = u.master_profile.bids
        master_data = {
            "master_id": u.master_profile.id,
            "description": u.master_profile.description,
            "categories": [c.name for c in u.master_profile.categories],
            "districts": [d.name for d in u.master_profile.districts],
            "total_bids": len(bids),
            "processed_orders": sum(1 for b in bids if b.status == BidStatus.ACCEPTED),
            "status": u.master_profile.status,
            "rating": u.master_profile.rating,
            "is_accredited": u.master_profile.is_accredited,
        }
    return {
        "id": u.id,
        "telegram_id": u.telegram_id,
        "role": u.role,
        "full_name": u.full_name,
        "username": u.username,
        "phone": u.phone_number,
        "points": u.points,
        "client_orders_count": len(u.orders_created),
        "master_data": master_data,
        "created_at": u.created_at,
    }


_USER_LOAD = (
    selectinload(User.master_profile).selectinload(MasterProfile.categories),
    selectinload(User.master_profile).selectinload(MasterProfile.districts),
    selectinload(User.master_profile).selectinload(MasterProfile.bids),
    selectinload(User.orders_created),
)


@app.get("/api/v1/users", dependencies=[Depends(verify_api_key)])
async def list_users(role: Optional[UserRole] = None, q: Optional[str] = None,
                     master_status: Optional[MasterStatus] = None, skip: int = 0, limit: int = 50):
    """Users with stats; server-side search (name / @username / phone / id / telegram id) and filters."""
    limit = max(1, min(limit, 200))
    conds = _user_filters(role, q, master_status)
    async with async_session_maker() as session:
        total = (await session.execute(select(func.count(User.id)).where(*conds))).scalar() or 0
        stmt = (select(User).options(*_USER_LOAD).where(*conds)
                .order_by(User.created_at.desc(), User.id.desc()).offset(skip).limit(limit))
        users = (await session.execute(stmt)).scalars().all()
        return {"total": total, "items": [_user_row(u) for u in users]}


@app.get("/api/v1/users/export", dependencies=[Depends(verify_api_key)])
async def export_users(role: Optional[UserRole] = None, q: Optional[str] = None,
                       master_status: Optional[MasterStatus] = None):
    conds = _user_filters(role, q, master_status)
    async with async_session_maker() as session:
        users = (await session.execute(
            select(User).options(*_USER_LOAD).where(*conds).order_by(User.id).limit(EXPORT_LIMIT)
        )).scalars().all()
    rows = []
    for u in users:
        r = _user_row(u)
        m = r["master_data"] or {}
        rows.append([r["id"], r["telegram_id"], _enum(r["role"]), r["full_name"], r["username"], r["phone"], r["points"],
                     r["client_orders_count"], _enum(m.get("status")), m.get("total_bids"), m.get("processed_orders"),
                     "; ".join(m.get("categories", [])), "; ".join(m.get("districts", [])), r["created_at"]])
    return _csv_response("users.csv",
                         ["id", "telegram_id", "role", "name", "username", "phone", "points", "client_orders",
                          "master_status", "bids", "accepted_bids", "categories", "districts", "created_at"], rows)


@app.get("/api/v1/users/{user_id}", dependencies=[Depends(verify_api_key)])
async def get_user_details(user_id: int):
    """Full user card: profile, recent orders / bids and the points history."""
    async with async_session_maker() as session:
        u = (await session.execute(select(User).options(*_USER_LOAD).where(User.id == user_id))).scalar_one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        row = _user_row(u)

        txs = (await session.execute(
            select(Transaction).where(Transaction.user_id == u.id)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc()).limit(30)
        )).scalars().all()
        orders = (await session.execute(
            select(Order).options(selectinload(Order.category)).where(Order.client_id == u.id)
            .order_by(Order.created_at.desc()).limit(10)
        )).scalars().all()
        bids = []
        if u.master_profile:
            bids = (await session.execute(
                select(Bid).where(Bid.master_id == u.master_profile.id).order_by(Bid.created_at.desc()).limit(10)
            )).scalars().all()
        referrals = (await session.execute(select(func.count(User.id)).where(User.referred_by == u.id))).scalar() or 0

        row.update({
            "referrals": referrals,
            "banned_until": u.banned_until,
            "transactions": [{"id": t.id, "amount": t.amount, "type": t.type, "description": t.description,
                              "date": t.created_at} for t in txs],
            "orders": [{"id": o.id, "category": o.category.name, "status": o.status, "budget": o.budget,
                        "created_at": o.created_at} for o in orders],
            "bids": [{"id": b.id, "order_id": b.order_id, "price": b.suggested_price, "status": b.status,
                      "created_at": b.created_at} for b in bids],
        })
        return row


@app.get("/api/v1/masters", dependencies=[Depends(verify_api_key)])
async def list_masters(status: Optional[MasterStatus] = None):
    """Returns a list of all masters, optionally filtered by status."""
    async with async_session_maker() as session:
        stmt = select(MasterProfile).options(selectinload(MasterProfile.user))
        if status:
            stmt = stmt.where(MasterProfile.status == status)
        
        masters = (await session.execute(stmt)).scalars().all()
        
        return [{
            "id": m.id,
            "user_id": m.user_id,
            "full_name": m.user.full_name,
            "status": m.status,
            "rating": m.rating,
            "is_accredited": m.is_accredited,
            "points": m.user.points,
            "registration_date": m.user.created_at
        } for m in masters]

@app.get("/api/v1/masters/{master_id}", dependencies=[Depends(verify_api_key)])
async def get_master_details(master_id: int):
    """Returns full details of a specific master."""
    async with async_session_maker() as session:
        stmt = select(MasterProfile).options(
            selectinload(MasterProfile.user),
            selectinload(MasterProfile.categories),
            selectinload(MasterProfile.districts)
        ).where(MasterProfile.id == master_id)
        
        master = (await session.execute(stmt)).scalar_one_or_none()
        if not master:
            raise HTTPException(status_code=404, detail="Master not found")
            
        return {
            "profile": {
                "id": master.id,
                "status": master.status,
                "description": master.description,
                "experience": master.experience,
                "rating": master.rating,
                "is_accredited": master.is_accredited,
                "work_photos": master.work_photos
            },
            "user": {
                "full_name": master.user.full_name,
                "username": master.user.username,
                "phone": master.user.phone_number,
                "points": master.user.points
            },
            "categories": [{"id": c.id, "name": c.name} for c in master.categories],
            "districts": [{"id": d.id, "name": d.name} for d in master.districts]
        }

@app.patch("/api/v1/masters/{master_id}", dependencies=[Depends(MODERATION)])
async def update_master_status(master_id: int, data: MasterUpdate, current_user: User = Depends(get_current_user)):
    """Updates master status or accreditation. Approving pays the welcome/referral bonuses exactly like the bot does."""
    notifications = []
    async with async_session_maker() as session:
        master = await session.get(MasterProfile, master_id)
        if not master:
            raise HTTPException(status_code=404, detail="Master not found")

        if data.status is not None:
            if data.status == MasterStatus.APPROVED:
                result = await billing.approve_master(session, master)
                if result.granted:
                    user = await session.get(User, master.user_id)
                    bonus = f"\n🎁 Вам начислено <b>{result.welcome} приветственных баллов</b>." if result.welcome else ""
                    notifications.append((user.telegram_id, f"🎉 <b>Ваш профиль мастера одобрен!</b>{bonus}\nТеперь вы можете откликаться на заказы."))
                    if result.inviter_telegram_id:
                        notifications.append((
                            result.inviter_telegram_id,
                            f"🎁 <b>Бонус за реферала!</b>\nПриглашенный вами мастер <b>{user.full_name}</b> прошёл проверку. "
                            f"Вам начислено <b>{result.inviter_bonus} баллов</b>!",
                        ))
            else:
                master.status = data.status
        if data.is_accredited is not None:
            master.is_accredited = data.is_accredited

        await log_action(session, "UPDATE_MASTER", f"Master #{master_id}: {data.model_dump_json(exclude_none=True)}", admin_id=current_user.id)
        await session.commit()

    for tg_id, text in notifications:
        await notify_user(tg_id, text)
    return {"status": "success", "master_id": master_id}

@app.post("/api/v1/masters/{master_id}/adjust-points", dependencies=[Depends(FINANCE)])
async def adjust_master_points(master_id: int, data: PointAdjustment, current_user: User = Depends(get_current_user)):
    """Manually adjust master points (add/remove). A balance can never become negative."""
    if data.amount == 0:
        raise HTTPException(status_code=400, detail="Amount must not be zero")
    async with async_session_maker() as session:
        # Get user linked to master
        stmt = select(User).join(MasterProfile).where(MasterProfile.id == master_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found for this master")

        try:
            user = await billing.adjust(session, user.id, data.amount, TransactionType.ADMIN_ADJUSTMENT, data.description)
        except billing.InsufficientFunds:
            raise HTTPException(status_code=400, detail="Insufficient balance: points cannot go below zero")
        await log_action(session, "ADJUST_POINTS", f"Master #{master_id}: {data.amount} ({data.description})", admin_id=current_user.id)
        await session.commit()
        return {"status": "success", "new_balance": user.points}

# --- ORDERS ---

def _order_filters(status, q, category_id, date_from, date_to):
    conds = []
    if status:
        conds.append(Order.status == status)
    if category_id:
        conds.append(Order.category_id == category_id)
    if date_from:
        conds.append(Order.created_at >= date_from)
    if date_to:
        conds.append(Order.created_at < date_to + timedelta(days=1))
    if q and q.strip():
        term = q.strip()
        like = f"%{term}%"
        parts = [Order.description.ilike(like),
                 exists().where(Category.id == Order.category_id, Category.name.ilike(like)),
                 exists().where(District.id == Order.district_id, District.name.ilike(like)),
                 exists().where(User.id == Order.client_id, or_(User.full_name.ilike(like), User.phone_number.ilike(like)))]
        if term.lstrip("#").isdigit() and int(term.lstrip("#")) <= INT32_MAX:
            parts.append(Order.id == int(term.lstrip("#")))
        conds.append(or_(*parts))
    return conds


@app.get("/api/v1/orders", dependencies=[Depends(verify_api_key)])
async def list_orders(status: Optional[OrderStatus] = None, q: Optional[str] = None,
                      category_id: Optional[int] = None, date_from: Optional[datetime] = None,
                      date_to: Optional[datetime] = None, skip: int = 0, limit: int = 50):
    """Orders with server-side search (id / text / category / district / client) and filters."""
    limit = max(1, min(limit, 200))
    conds = _order_filters(status, q, category_id, date_from, date_to)
    bids_count = (select(func.count(Bid.id)).where(Bid.order_id == Order.id).correlate(Order).scalar_subquery())
    async with async_session_maker() as session:
        total = (await session.execute(select(func.count(Order.id)).where(*conds))).scalar() or 0
        stmt = (select(Order, bids_count)
                .options(selectinload(Order.category), selectinload(Order.district), selectinload(Order.client))
                .where(*conds).order_by(Order.created_at.desc(), Order.id.desc()).offset(skip).limit(limit))
        items = [{
            "id": o.id,
            "client_id": o.client_id,
            "client_name": o.client.full_name,
            "category": o.category.name,
            "district": o.district.name if o.district else None,
            "status": o.status,
            "budget": o.budget,
            "bids_count": n,
            "created_at": o.created_at,
        } for o, n in (await session.execute(stmt)).all()]
        return {"total": total, "items": items}


@app.get("/api/v1/orders/export", dependencies=[Depends(verify_api_key)])
async def export_orders(status: Optional[OrderStatus] = None, q: Optional[str] = None,
                        category_id: Optional[int] = None, date_from: Optional[datetime] = None,
                        date_to: Optional[datetime] = None):
    conds = _order_filters(status, q, category_id, date_from, date_to)
    bids_count = (select(func.count(Bid.id)).where(Bid.order_id == Order.id).correlate(Order).scalar_subquery())
    async with async_session_maker() as session:
        res = (await session.execute(
            select(Order, bids_count)
            .options(selectinload(Order.category), selectinload(Order.district), selectinload(Order.client))
            .where(*conds).order_by(Order.id).limit(EXPORT_LIMIT))).all()
    rows = [[o.id, _enum(o.status), o.category.name, o.district.name if o.district else "", o.client.full_name,
             o.client.phone_number, o.budget, n, o.description, o.created_at] for o, n in res]
    return _csv_response("orders.csv", ["id", "status", "category", "district", "client", "client_phone", "budget",
                                        "bids", "description", "created_at"], rows)


@app.get("/api/v1/orders/{order_id}", dependencies=[Depends(verify_api_key)])
async def get_order_details(order_id: int):
    """Returns full order details including bids."""
    async with async_session_maker() as session:
        stmt = select(Order).options(
            selectinload(Order.category),
            selectinload(Order.district),
            selectinload(Order.client),
            selectinload(Order.bids).selectinload(Bid.master).selectinload(MasterProfile.user)
        ).where(Order.id == order_id)

        order = (await session.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        return {
            "id": order.id,
            "status": order.status,
            "category": order.category.name,
            "district": order.district.name if order.district else None,
            "description": order.description,
            "budget": order.budget,
            "created_at": order.created_at,
            "client": {
                "id": order.client.id,
                "name": order.client.full_name,
                "phone": order.client.phone_number
            },
            "bids": [{
                "id": b.id,
                "master_user_id": b.master.user.id,
                "master_name": b.master.user.full_name,
                "price": b.suggested_price,
                "status": b.status,
                "message": b.message,
                "created_at": b.created_at,
            } for b in order.bids]
        }


@app.post("/api/v1/orders/{order_id}/cancel", dependencies=[Depends(MODERATION)])
async def admin_cancel_order(order_id: int, current_user: User = Depends(get_current_user)):
    """Cancels an open order (spam, fraud) and refunds the bid fees of every master who responded."""
    async with async_session_maker() as session:
        order = (await session.execute(
            select(Order).options(selectinload(Order.client)).where(Order.id == order_id).with_for_update()
        )).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED):
            raise HTTPException(status_code=400, detail="Заказ уже завершён или отменён")
        client_tg = order.client.telegram_id
        notices = await order_service.cancel_order(session, order_id, "заявка отменена администратором")
        await log_action(session, "CANCEL_ORDER", f"Order #{order_id} cancelled by admin, refunds to {len(notices)} master(s)",
                         admin_id=current_user.id)
        await session.commit()

    await notify_user(client_tg, f"⚠️ Ваша заявка №{order_id} была отменена администратором.")
    for n in notices:
        extra = f" Возвращено {n.refunded} баллов." if n.refunded else ""
        await notify_user(n.master_telegram_id, f"⚠️ Заявка №{order_id} отменена администратором.{extra}")
    return {"status": "success", "refunded_masters": len(notices)}


# --- CATEGORIES & DISTRICTS ---

@app.get("/api/v1/categories", dependencies=[Depends(verify_api_key)])
async def list_categories(skip: int = 0, limit: int = 500):
    async with async_session_maker() as session:
        # Total count
        total = (await session.execute(select(func.count(Category.id)))).scalar() or 0
        
        # Items
        stmt = select(Category).order_by(Category.name.asc()).offset(skip).limit(limit)
        cats = (await session.execute(stmt)).scalars().all()
        return {"total": total, "items": cats}

@app.post("/api/v1/categories", dependencies=[Depends(SUPERADMIN)])
async def add_category(data: NameUpdate):
    async with async_session_maker() as session:
        session.add(Category(name=data.name))
        await session.commit()
        return {"status": "created"}

@app.delete("/api/v1/categories/{cat_id}", dependencies=[Depends(SUPERADMIN)])
async def delete_category(cat_id: int):
    async with async_session_maker() as session:
        cat = await session.get(Category, cat_id)
        if cat:
            await session.delete(cat)
            await session.commit()
            return {"status": "deleted"}
        raise HTTPException(status_code=404)

@app.get("/api/v1/districts", dependencies=[Depends(verify_api_key)])
async def list_districts(skip: int = 0, limit: int = 500):
    async with async_session_maker() as session:
        # Total count
        total = (await session.execute(select(func.count(District.id)))).scalar() or 0
        
        # Items
        stmt = select(District).order_by(District.name.asc()).offset(skip).limit(limit)
        dists = (await session.execute(stmt)).scalars().all()
        return {"total": total, "items": dists}

@app.post("/api/v1/districts", dependencies=[Depends(SUPERADMIN)])
async def add_district(data: NameUpdate):
    async with async_session_maker() as session:
        session.add(District(name=data.name))
        await session.commit()
        return {"status": "created"}

@app.delete("/api/v1/districts/{dist_id}", dependencies=[Depends(SUPERADMIN)])
async def delete_district(dist_id: int):
    async with async_session_maker() as session:
        dist = await session.get(District, dist_id)
        if dist:
            await session.delete(dist)
            await session.commit()
            return {"status": "deleted"}
        raise HTTPException(status_code=404)

# --- FINANCES ---

@app.get("/api/v1/topups", dependencies=[Depends(verify_api_key)])
async def list_topup_requests(status: Optional[str] = "PENDING", skip: int = 0, limit: int = 50):
    async with async_session_maker() as session:
        # Total count
        count_stmt = select(func.count(TopUpRequest.id))
        if status:
            count_stmt = count_stmt.where(TopUpRequest.status == status)
        total = (await session.execute(count_stmt)).scalar() or 0

        # Items
        stmt = select(TopUpRequest).options(selectinload(TopUpRequest.user))
        if status:
            stmt = stmt.where(TopUpRequest.status == status)
        
        stmt = stmt.order_by(TopUpRequest.created_at.desc()).offset(skip).limit(limit)
        reqs = (await session.execute(stmt)).scalars().all()
        
        items = [{
            "id": r.id,
            "user_name": r.user.full_name,
            "amount": r.amount,
            "method": r.method,
            "receipt": r.receipt_data,
            "created_at": r.created_at
        } for r in reqs]
        
        return {"total": total, "items": items}

@app.patch("/api/v1/topups/{request_id}", dependencies=[Depends(FINANCE)])
async def review_topup(request_id: int, data: TopUpReview, current_user: User = Depends(get_current_user)):
    if data.status not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="status must be APPROVED or REJECTED")
    async with async_session_maker() as session:
        # Lock the request row so two admins cannot approve the same top-up twice
        req = (await session.execute(
            select(TopUpRequest).where(TopUpRequest.id == request_id).with_for_update()
        )).scalar_one_or_none()
        if not req or req.status != "PENDING":
            raise HTTPException(status_code=404, detail="Request not found or already processed")

        user = (await session.execute(
            select(User).where(User.id == req.user_id).with_for_update()
        )).scalar_one()

        if data.status == "APPROVED":
            req.status = "APPROVED"
            await billing.credit(session, user.id, req.amount, TransactionType.TOPUP,
                                 f"Пополнение баланса через {req.method} (Admin API)")
            message = (
                f"✅ <b>Баланс пополнен!</b>\n\nСумма: <b>{req.amount} ₸</b>\nСпособ: {req.method}\n"
                f"Ваш текущий баланс: <b>{user.points} ₸</b>"
            )
        else:
            req.status = "REJECTED"
            message = (
                f"❌ <b>Заявка на пополнение отклонена</b>\n\nСумма: {req.amount} ₸\n\n"
                "Если у вас есть вопросы, обратитесь в поддержку."
            )

        await log_action(session, f"TOPUP_{data.status}", f"Request #{request_id} reviewed. User: {user.full_name}, Amount: {req.amount}", admin_id=current_user.id)
        telegram_id = user.telegram_id
        await session.commit()

    # Notify only AFTER the data is safely committed
    await notify_user(telegram_id, message)
    return {"status": "success"}

@app.get("/api/v1/transactions", dependencies=[Depends(verify_api_key)])
async def list_transactions(skip: int = 0, limit: int = 50):
    """Returns transactions with pagination."""
    async with async_session_maker() as session:
        # Total count
        total = (await session.execute(select(func.count(Transaction.id)))).scalar() or 0

        # Items
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.user))
            .order_by(Transaction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        txs = (await session.execute(stmt)).scalars().all()
        
        items = [{
            "id": t.id,
            "user": t.user.full_name,
            "amount": t.amount,
            "type": t.type,
            "description": t.description,
            "date": t.created_at
        } for t in txs]
        
        return {"total": total, "items": items}

@app.post("/api/v1/finance/bulk-adjust-points", dependencies=[Depends(FINANCE)])
async def bulk_adjust_points(data: BulkPointAdjustment, current_user: User = Depends(get_current_user)):
    """Adjust points for multiple masters or all of them."""
    if data.amount == 0:
        raise HTTPException(status_code=400, detail="Amount must not be zero")
    notifications = []
    async with async_session_maker() as session:
        if data.all_masters:
            # Get all users who have a master profile
            stmt = select(User).join(MasterProfile)
            users = (await session.execute(stmt)).scalars().all()
        elif data.master_ids:
            stmt = select(User).join(MasterProfile).where(MasterProfile.id.in_(data.master_ids))
            users = (await session.execute(stmt)).scalars().all()
        else:
            raise HTTPException(status_code=400, detail="No masters specified")

        skipped = 0
        for user in users:
            try:
                await billing.adjust(session, user.id, data.amount, TransactionType.ADMIN_ADJUSTMENT, data.description)
            except billing.InsufficientFunds:
                skipped += 1  # a negative adjustment must not push a balance below zero
                continue
            notifications.append((
                user.telegram_id,
                f"💰 <b>Начисление баллов</b>\n\nСумма: <b>{data.amount} ₸</b>\nОписание: {data.description}\n\n"
                f"Ваш текущий баланс: <b>{user.points} ₸</b>"
            ))

        await log_action(session, "BULK_ADJUST_POINTS", f"Amount: {data.amount}, Users: {len(notifications)}, Skipped: {skipped}, Reason: {data.description}", admin_id=current_user.id)
        await session.commit()

    # Notify only after commit; small pause to respect Telegram rate limits
    for tg_id, text in notifications:
        await notify_user(tg_id, text)
        await asyncio.sleep(0.05)
    return {"status": "success", "count": len(notifications), "skipped": skipped}

@app.get("/api/v1/logs", dependencies=[Depends(SUPERADMIN)])
async def list_admin_logs(skip: int = 0, limit: int = 50):
    """Returns administrative logs with pagination."""
    async with async_session_maker() as session:
        total = (await session.execute(select(func.count(AdminLog.id)))).scalar() or 0
        stmt = (
            select(AdminLog)
            .outerjoin(User, AdminLog.admin_id == User.id)
            .add_columns(User.full_name.label("admin_name"))
            .order_by(AdminLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        results = (await session.execute(stmt)).all()
        
        items = []
        for log, admin_name in results:
            items.append({
                "id": log.id,
                "admin_id": log.admin_id,
                "admin_name": admin_name or "Bot/System",
                "action": log.action,
                "details": log.details,
                "created_at": log.created_at
            })
            
        return {"total": total, "items": items}

# --- BACKUP ENDPOINTS ---

@app.get("/api/v1/backups", dependencies=[Depends(SUPERADMIN)])
async def list_backups():
    return backup_util.list_backups()

@app.post("/api/v1/backups", dependencies=[Depends(SUPERADMIN)])
async def trigger_backup(current_user: User = Depends(get_current_user)):
    filename = await backup_util.create_backup()
    async with async_session_maker() as session:
        await log_action(session, "CREATE_BACKUP", f"Manual backup created: {filename}", admin_id=current_user.id)
        await session.commit()
    return {"status": "success", "filename": filename}

@app.get("/api/v1/backups/{filename}", dependencies=[Depends(SUPERADMIN)])
async def download_backup(filename: str):
    path = backup_util.get_backup_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Backup file not found")
    return FileResponse(path, filename=filename, media_type='application/json')

@app.delete("/api/v1/backups/{filename}", dependencies=[Depends(SUPERADMIN)])
async def delete_backup(filename: str, current_user: User = Depends(get_current_user)):
    success = backup_util.delete_backup(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Backup file not found")
    async with async_session_maker() as session:
        await log_action(session, "DELETE_BACKUP", f"Backup deleted: {filename}", admin_id=current_user.id)
        await session.commit()
    return {"status": "success"}
