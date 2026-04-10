import enum
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import BigInteger, String, ForeignKey, Enum as SqlEnum, DateTime, Integer, Float, Boolean, Table, Column, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base

class UserRole(enum.Enum):
    CLIENT = "CLIENT"
    MASTER = "MASTER"
    ADMIN = "ADMIN"

class MasterStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class OrderStatus(enum.Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class TransactionType(enum.Enum):
    REFERRAL_BONUS = "REFERRAL_BONUS"
    CONTACT_FEE = "CONTACT_FEE"
    RATING_BONUS = "RATING_BONUS"
    WITHDRAWAL = "WITHDRAWAL"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"
    REFUND = "REFUND"

# Association table for Master - Category subscriptions
master_category_subscriptions = Table(
    "master_category_subscriptions",
    Base.metadata,
    Column("master_profile_id", ForeignKey("master_profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for Master - District areas
master_district_areas = Table(
    "master_district_areas",
    Base.metadata,
    Column("master_profile_id", ForeignKey("master_profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("district_id", ForeignKey("districts.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), default=UserRole.CLIENT)
    
    # Referral system
    referred_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    points: Mapped[int] = mapped_column(default=0)
    banned_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    agreed_to_terms: Mapped[bool] = mapped_column(default=False)
    
    # Settings
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    dnd_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True) # e.g. "18:00"
    dnd_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)   # e.g. "08:00"
    visible_for_new_orders: Mapped[bool] = mapped_column(default=True)
    
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    master_profile: Mapped["MasterProfile"] = relationship(back_populates="user", uselist=False)
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user")
    orders_created: Mapped[List["Order"]] = relationship(back_populates="client")

class Category(Base):
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    masters: Mapped[List["MasterProfile"]] = relationship(
        secondary=master_category_subscriptions, back_populates="categories"
    )
    orders: Mapped[List["Order"]] = relationship(back_populates="category")

class District(Base):
    __tablename__ = "districts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    
    masters: Mapped[List["MasterProfile"]] = relationship(
        secondary=master_district_areas, back_populates="districts"
    )
    orders: Mapped[List["Order"]] = relationship(back_populates="district")

class MasterProfile(Base):
    __tablename__ = "master_profiles"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    status: Mapped[MasterStatus] = mapped_column(SqlEnum(MasterStatus), default=MasterStatus.PENDING)
    description: Mapped[Optional[str]] = mapped_column(Text)
    experience: Mapped[Optional[str]] = mapped_column(String(255))
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    is_accredited: Mapped[bool] = mapped_column(default=False)
    
    # Portfolio
    work_photos: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    
    user: Mapped["User"] = relationship(back_populates="master_profile")
    categories: Mapped[List["Category"]] = relationship(
        secondary=master_category_subscriptions, back_populates="masters"
    )
    districts: Mapped[List["District"]] = relationship(
        secondary=master_district_areas, back_populates="masters"
    )
    bids: Mapped[List["Bid"]] = relationship(back_populates="master")

class Order(Base):
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    district_id: Mapped[Optional[int]] = mapped_column(ForeignKey("districts.id"))
    
    description: Mapped[str] = mapped_column(Text)
    budget: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[OrderStatus] = mapped_column(SqlEnum(OrderStatus), default=OrderStatus.NEW)
    photo_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    client: Mapped["User"] = relationship(back_populates="orders_created")
    category: Mapped["Category"] = relationship(back_populates="orders")
    district: Mapped[Optional["District"]] = relationship(back_populates="orders")
    bids: Mapped[List["Bid"]] = relationship(back_populates="order")
    review: Mapped[Optional["Review"]] = relationship(back_populates="order", uselist=False)

class Bid(Base):
    __tablename__ = "bids"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    master_id: Mapped[int] = mapped_column(ForeignKey("master_profiles.id"))
    suggested_price: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    message: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    order: Mapped["Order"] = relationship(back_populates="bids")
    master: Mapped["MasterProfile"] = relationship(back_populates="bids")

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text)
    is_replied: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    user: Mapped["User"] = relationship()

class SupportChat(Base):
    __tablename__ = "support_chats"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_tid: Mapped[int] = mapped_column(BigInteger)
    admin_tid: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class Review(Base):
    __tablename__ = "reviews"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    order: Mapped["Order"] = relationship(back_populates="review")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[TransactionType] = mapped_column(SqlEnum(TransactionType))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"))
    
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    user: Mapped["User"] = relationship(back_populates="transactions")

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    crypto_enabled: Mapped[bool] = mapped_column(default=False)
    crypto_address: Mapped[Optional[str]] = mapped_column(String(255))
    bank_enabled: Mapped[bool] = mapped_column(default=False)
    bank_details: Mapped[Optional[str]] = mapped_column(Text)

class TopUpRequest(Base):
    __tablename__ = "topup_requests"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(50)) # 'CRYPTO' or 'BANK'
    status: Mapped[str] = mapped_column(String(20), default="PENDING") # PENDING, APPROVED, REJECTED
    receipt_data: Mapped[Optional[str]] = mapped_column(Text) # Text or File ID
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    user: Mapped["User"] = relationship()


