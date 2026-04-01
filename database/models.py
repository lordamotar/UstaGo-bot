from typing import List, Optional
from sqlalchemy import BigInteger, Column, Integer, String, Text, ForeignKey, Enum, Boolean, Table
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, relationship
from enum import Enum as PyEnum

Base = declarative_base()

class UserRole(PyEnum):
    CLIENT = "client"
    MASTER = "master"
    ADMIN = "admin"

class MasterStatus(PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# Many-to-Many association table for Masters and Categories
master_categories = Table(
    'master_category_subscriptions',
    Base.metadata,
    Column('master_id', Integer, ForeignKey('master_profiles.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id'), primary_key=True)
)

class User(Base):
    """
    Core User table representing a Telegram user.
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    phone_number: Mapped[Optional[str]] = mapped_column(String(20))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.CLIENT)
    points: Mapped[int] = mapped_column(Integer, default=100)  # Initial bonus
    
    # Relationships
    master_profile: Mapped["MasterProfile"] = relationship("MasterProfile", back_populates="user", uselist=False)
    orders_placed: Mapped[List["Order"]] = relationship("Order", back_populates="client")


class Category(Base):
    """
    Two-tier category taxonomy (e.g. "Мастер на час" -> "Электрик")
    """
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('categories.id'))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    masters: Mapped[List["MasterProfile"]] = relationship("MasterProfile", secondary=master_categories, back_populates="categories")


class MasterProfile(Base):
    """
    Profile information specifically for Masters.
    """
    __tablename__ = 'master_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    status: Mapped[MasterStatus] = mapped_column(Enum(MasterStatus), default=MasterStatus.PENDING)
    description: Mapped[Optional[str]] = mapped_column(Text)
    experience: Mapped[Optional[str]] = mapped_column(String(100))
    rating: Mapped[float] = mapped_column(default=0.0)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="master_profile")
    categories: Mapped[List["Category"]] = relationship("Category", secondary=master_categories, back_populates="masters")


class OrderStatus(PyEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Order(Base):
    """
    Represents a client's job request dispatched to Masters.
    """
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey('categories.id'), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Optional[str]] = mapped_column(String(50))  # Free-form or numeric
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.OPEN)

    # Relationships
    client: Mapped["User"] = relationship("User", back_populates="orders_placed")
    category: Mapped["Category"] = relationship("Category")
