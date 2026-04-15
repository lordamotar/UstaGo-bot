from fastapi import FastAPI, Depends, HTTPException, Body
from sqlalchemy import select, func, update
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
from fastapi.responses import FileResponse
import admin_api.backups as backup_util
import asyncio
import sentry_sdk
import random
import time

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
SECRET_KEY = getattr(config, "JWT_SECRET_KEY", "your-secret-key-change-it-in-env")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# --- AUTH UTILS ---

# 2FA temporary code storage: {username: {"code": "123456", "expires": timestamp}}
_2fa_codes: dict = {}

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

# --- AUTH ENDPOINTS ---

@app.post("/api/v1/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    async with async_session_maker() as session:
        stmt = select(User).where(User.username == form_data.username)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        print(f"DEBUG LOGIN: Attempt for username='{form_data.username}'")
        if not user:
            print(f"DEBUG LOGIN: User '{form_data.username}' NOT FOUND in database")
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        is_valid = verify_password(form_data.password, user.hashed_password)
        print(f"DEBUG LOGIN: User found. ID={user.id}, Role={user.role}")
        print(f"DEBUG LOGIN: Password verification result: {is_valid}")

        if not is_valid:
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        
        # Generate 2FA code and send to Telegram
        code = str(random.randint(100000, 999999))
        _2fa_codes[user.username] = {
            "code": code,
            "expires": time.time() + 300  # 5 minutes TTL
        }
        
        # Send code via Telegram
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
            print(f"Failed to send 2FA code to {user.telegram_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to send 2FA code")
        
        return {"requires_2fa": True, "message": "2FA code sent to your Telegram"}

class TwoFAVerify(BaseModel):
    username: str
    code: str

@app.post("/api/v1/auth/verify-2fa")
async def verify_2fa(data: TwoFAVerify):
    stored = _2fa_codes.get(data.username)
    
    if not stored:
        raise HTTPException(status_code=400, detail="No 2FA code requested. Please login again.")
    
    if time.time() > stored["expires"]:
        del _2fa_codes[data.username]
        raise HTTPException(status_code=400, detail="2FA code expired. Please login again.")
    
    if stored["code"] != data.code:
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    
    # Code is valid — clean up and issue JWT
    del _2fa_codes[data.username]
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v1/auth/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role
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
                .where(*where_clause, Bid.status == 'ACCEPTED')\
                .group_by(func.date(Order.created_at), User.full_name)
        else:
            # Default: split by 'Total' or apply master_id filter
            stmt = select(func.date(Order.created_at).label("day"), func.count(Order.id))
            if master_id:
                stmt = stmt.join(Bid).where(Bid.master_id == master_id, Bid.status == 'ACCEPTED')
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

@app.patch("/api/v1/settings", dependencies=[Depends(verify_api_key)])
async def update_settings(data: SystemSettingsUpdate):
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
        
        await log_action(session, "UPDATE_SETTINGS", f"Settings updated: {data.json(exclude_none=True)}", admin_id=current_user.id)
        await session.commit()
        return {"status": "success"}

@app.get("/api/v1/users", dependencies=[Depends(verify_api_key)])
async def list_users(role: Optional[UserRole] = None, skip: int = 0, limit: int = 50):
    """Returns a list of all users with detailed stats supporting pagination."""
    async with async_session_maker() as session:
        # Total count
        count_stmt = select(func.count(User.id))
        if role:
            count_stmt = count_stmt.where(User.role == role)
        total = (await session.execute(count_stmt)).scalar() or 0

        # Items
        stmt = select(User).options(
            selectinload(User.master_profile).selectinload(MasterProfile.categories),
            selectinload(User.master_profile).selectinload(MasterProfile.districts),
            selectinload(User.master_profile).selectinload(MasterProfile.bids).selectinload(Bid.order),
            selectinload(User.orders_created)
        )
        if role:
            stmt = stmt.where(User.role == role)
        
        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
            
        users = (await session.execute(stmt)).scalars().all()
        
        items = []
        for u in users:
            client_orders_count = len(u.orders_created)
            
            master_data = None
            if u.master_profile:
                total_bids = len(u.master_profile.bids)
                accepted_bids = sum(1 for b in u.master_profile.bids if b.status == 'ACCEPTED')
                
                master_data = {
                    "master_id": u.master_profile.id,
                    "description": u.master_profile.description,
                    "categories": [c.name for c in u.master_profile.categories],
                    "districts": [d.name for d in u.master_profile.districts],
                    "total_bids": total_bids,
                    "processed_orders": accepted_bids,
                    "status": u.master_profile.status,
                    "rating": u.master_profile.rating,
                    "is_accredited": u.master_profile.is_accredited
                }
            
            items.append({
                "id": u.id,
                "role": u.role,
                "full_name": u.full_name,
                "username": u.username,
                "phone": u.phone_number,
                "points": u.points,
                "client_orders_count": client_orders_count,
                "master_data": master_data,
                "created_at": u.created_at
            })
        return {"total": total, "items": items}

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

@app.patch("/api/v1/masters/{master_id}", dependencies=[Depends(verify_api_key)])
async def update_master_status(master_id: int, data: MasterUpdate):
    """Updates master status or accreditation."""
    async with async_session_maker() as session:
        master = (await session.get(MasterProfile, master_id))
        if not master:
            raise HTTPException(status_code=404, detail="Master not found")
            
        if data.status is not None:
            master.status = data.status
        if data.is_accredited is not None:
            master.is_accredited = data.is_accredited
            
        await session.commit()
        return {"status": "success", "master_id": master_id}

@app.post("/api/v1/masters/{master_id}/adjust-points", dependencies=[Depends(verify_api_key)])
async def adjust_master_points(master_id: int, data: PointAdjustment):
    """Manually adjust master points (add/remove)."""
    async with async_session_maker() as session:
        # Get user linked to master
        stmt = select(User).join(MasterProfile).where(MasterProfile.id == master_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found for this master")
            
        user.points += data.amount
        session.add(Transaction(
            user_id=user.id,
            amount=data.amount,
            type=TransactionType.ADMIN_ADJUSTMENT,
            description=data.description
        ))
        
        await session.commit()
        return {"status": "success", "new_balance": user.points}

# --- ORDERS ---

@app.get("/api/v1/orders", dependencies=[Depends(verify_api_key)])
async def list_orders(status: Optional[OrderStatus] = None, skip: int = 0, limit: int = 50):
    """Returns a list of orders supporting pagination."""
    async with async_session_maker() as session:
        # Total count
        count_stmt = select(func.count(Order.id))
        if status:
            count_stmt = count_stmt.where(Order.status == status)
        total = (await session.execute(count_stmt)).scalar() or 0

        # Items
        stmt = select(Order).options(selectinload(Order.category), selectinload(Order.district))
        if status:
            stmt = stmt.where(Order.status == status)
        
        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        
        orders = (await session.execute(stmt)).scalars().all()
        
        items = [{
            "id": o.id,
            "client_id": o.client_id,
            "category": o.category.name,
            "district": o.district.name if o.district else None,
            "status": o.status,
            "budget": o.budget,
            "created_at": o.created_at
        } for o in orders]
        
        return {"total": total, "items": items}

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
            "description": order.description,
            "budget": order.budget,
            "client": {
                "id": order.client.id,
                "name": order.client.full_name,
                "phone": order.client.phone_number
            },
            "bids": [{
                "id": b.id,
                "master_name": b.master.user.full_name,
                "price": b.suggested_price,
                "status": b.status,
                "message": b.message
            } for b in order.bids]
        }

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

@app.post("/api/v1/categories", dependencies=[Depends(verify_api_key)])
async def add_category(data: NameUpdate):
    async with async_session_maker() as session:
        session.add(Category(name=data.name))
        await session.commit()
        return {"status": "created"}

@app.delete("/api/v1/categories/{cat_id}", dependencies=[Depends(verify_api_key)])
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

@app.post("/api/v1/districts", dependencies=[Depends(verify_api_key)])
async def add_district(data: NameUpdate):
    async with async_session_maker() as session:
        session.add(District(name=data.name))
        await session.commit()
        return {"status": "created"}

@app.delete("/api/v1/districts/{dist_id}", dependencies=[Depends(verify_api_key)])
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

@app.patch("/api/v1/topups/{request_id}", dependencies=[Depends(verify_api_key)])
async def review_topup(request_id: int, data: TopUpReview):
    async with async_session_maker() as session:
        req = await session.get(TopUpRequest, request_id)
        if not req or req.status != "PENDING":
            raise HTTPException(status_code=404, detail="Request not found or already processed")
            
        user = await session.get(User, req.user_id)
        
        if data.status == "APPROVED":
            req.status = "APPROVED"
            user.points += req.amount
            session.add(Transaction(
                user_id=user.id,
                amount=req.amount,
                type=TransactionType.REFUND, # Positive adjustment
                description=f"Пополнение баланса через {req.method} (Admin API)"
            ))
            # Notification
            await notify_user(
                user.telegram_id, 
                f"✅ <b>Баланс пополнен!</b>\n\nСумма: <b>{req.amount} ₸</b>\nСпособ: {req.method}\nВаш текущий баланс: <b>{user.points} ₸</b>"
            )
        else:
            req.status = "REJECTED"
            await notify_user(
                user.telegram_id, 
                f"❌ <b>Заявка на пополнение отклонена</b>\n\nСумма: {req.amount} ₸\n\nЕсли у вас есть вопросы, обратитесь в поддержку."
            )
            
        await log_action(session, f"TOPUP_{data.status}", f"Request #{request_id} reviewed. User: {user.full_name}, Amount: {req.amount}", admin_id=current_user.id)
        await session.commit()
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

@app.post("/api/v1/finance/bulk-adjust-points", dependencies=[Depends(verify_api_key)])
async def bulk_adjust_points(data: BulkPointAdjustment):
    """Adjust points for multiple masters or all of them."""
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
            
        for user in users:
            user.points += data.amount
            session.add(Transaction(
                user_id=user.id,
                amount=data.amount,
                type=TransactionType.ADMIN_ADJUSTMENT,
                description=data.description
            ))
            # Notification
            await notify_user(
                user.telegram_id,
                f"💰 <b>Начисление баллов</b>\n\nСумма: <b>{data.amount} ₸</b>\nОписание: {data.description}\n\nВаш текущий баланс: <b>{user.points} ₸</b>"
            )
            
        await log_action(session, "BULK_ADJUST_POINTS", f"Amount: {data.amount}, Users: {len(users)}, Reason: {data.description}", admin_id=current_user.id)
        await session.commit()
        return {"status": "success", "count": len(users)}

@app.get("/api/v1/logs", dependencies=[Depends(verify_api_key)])
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

@app.get("/api/v1/backups", dependencies=[Depends(verify_api_key)])
async def list_backups():
    return backup_util.list_backups()

@app.post("/api/v1/backups", dependencies=[Depends(verify_api_key)])
async def trigger_backup(current_user: User = Depends(get_current_user)):
    filename = await backup_util.create_backup()
    async with async_session_maker() as session:
        await log_action(session, "CREATE_BACKUP", f"Manual backup created: {filename}", admin_id=current_user.id)
        await session.commit()
    return {"status": "success", "filename": filename}

@app.get("/api/v1/backups/{filename}", dependencies=[Depends(verify_api_key)])
async def download_backup(filename: str):
    path = backup_util.get_backup_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Backup file not found")
    return FileResponse(path, filename=filename, media_type='application/json')

@app.delete("/api/v1/backups/{filename}", dependencies=[Depends(verify_api_key)])
async def delete_backup(filename: str, current_user: User = Depends(get_current_user)):
    success = backup_util.delete_backup(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Backup file not found")
    async with async_session_maker() as session:
        await log_action(session, "DELETE_BACKUP", f"Backup deleted: {filename}", admin_id=current_user.id)
        await session.commit()
    return {"status": "success"}
