from fastapi import FastAPI, Depends, HTTPException, Body
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from database.engine import async_session_maker
from database.models import User, MasterProfile, Order, OrderStatus, UserRole, MasterStatus, Category, District, Transaction, TransactionType, TopUpRequest, Bid
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from fastapi.security import APIKeyHeader
from bot.core.config import config

app = FastAPI(title="UstaGo Admin API")

# Security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    # Use the first ADMIN_ID or a dedicated secret from env as the key for now
    # Ideally, add ADMIN_API_KEY to .env
    expected_key = getattr(config, "ADMIN_API_KEY", str(config.ADMIN_IDS[0]))
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

# Настройка CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
                "new": new_orders
            }
        }

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

# --- ENDPOINTS ---

@app.get("/api/v1/users", dependencies=[Depends(verify_api_key)])
async def list_users(role: Optional[UserRole] = None):
    """Returns a list of all users with detailed stats."""
    async with async_session_maker() as session:
        stmt = select(User).options(
            selectinload(User.master_profile).selectinload(MasterProfile.categories),
            selectinload(User.master_profile).selectinload(MasterProfile.bids).selectinload(Bid.order),
            selectinload(User.orders_created)
        )
        if role:
            stmt = stmt.where(User.role == role)
            
        users = (await session.execute(stmt)).scalars().all()
        
        result = []
        for u in users:
            client_orders_count = len(u.orders_created)
            
            master_data = None
            if u.master_profile:
                # В UstaGo статус обработанного заказа обычно 'ACCEPTED' (или 'COMPLETED' для самого заказа)
                # Давайте просто посчитаем кол-во заявок (bids) и сколько из них 'ACCEPTED'
                total_bids = len(u.master_profile.bids)
                accepted_bids = sum(1 for b in u.master_profile.bids if b.status == 'ACCEPTED')
                
                master_data = {
                    "master_id": u.master_profile.id,
                    "description": u.master_profile.description,
                    "categories": [c.name for c in u.master_profile.categories],
                    "total_bids": total_bids,
                    "processed_orders": accepted_bids,
                    "status": u.master_profile.status,
                    "rating": u.master_profile.rating,
                    "is_accredited": u.master_profile.is_accredited
                }
            
            result.append({
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
        return result

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
async def list_orders(status: Optional[OrderStatus] = None):
    """Returns a list of orders."""
    async with async_session_maker() as session:
        stmt = select(Order).options(selectinload(Order.category), selectinload(Order.district))
        if status:
            stmt = stmt.where(Order.status == status)
        
        orders = (await session.execute(stmt)).scalars().all()
        
        return [{
            "id": o.id,
            "client_id": o.client_id,
            "category": o.category.name,
            "district": o.district.name if o.district else None,
            "status": o.status,
            "budget": o.budget,
            "created_at": o.created_at
        } for o in orders]

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
async def list_categories():
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category))).scalars().all()
        return cats

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
async def list_districts():
    async with async_session_maker() as session:
        dists = (await session.execute(select(District))).scalars().all()
        return dists

@app.post("/api/v1/districts", dependencies=[Depends(verify_api_key)])
async def add_district(data: NameUpdate):
    async with async_session_maker() as session:
        session.add(District(name=data.name))
        await session.commit()
        return {"status": "created"}

# --- FINANCES ---

@app.get("/api/v1/topups", dependencies=[Depends(verify_api_key)])
async def list_topup_requests(status: Optional[str] = "PENDING"):
    async with async_session_maker() as session:
        stmt = select(TopUpRequest).options(selectinload(TopUpRequest.user))
        if status:
            stmt = stmt.where(TopUpRequest.status == status)
        
        reqs = (await session.execute(stmt)).scalars().all()
        return [{
            "id": r.id,
            "user_name": r.user.full_name,
            "amount": r.amount,
            "method": r.method,
            "receipt": r.receipt_data,
            "created_at": r.created_at
        } for r in reqs]

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
        else:
            req.status = "REJECTED"
            
        await session.commit()
        return {"status": "success"}

@app.get("/api/v1/transactions", dependencies=[Depends(verify_api_key)])
async def list_transactions(limit: int = 50):
    async with async_session_maker() as session:
        stmt = select(Transaction).options(selectinload(Transaction.user)).order_by(Transaction.created_at.desc()).limit(limit)
        txs = (await session.execute(stmt)).scalars().all()
        return [{
            "id": t.id,
            "user": t.user.full_name,
            "amount": t.amount,
            "type": t.type,
            "description": t.description,
            "date": t.created_at
        } for t in txs]
