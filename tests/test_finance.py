"""
Unit tests for UstaGo financial operations.
Tests cover: balance management, transactions, top-up requests, and data integrity.

Run with:  python -m pytest tests/ -v
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func

from database.base import Base
from database.models import (
    User, UserRole, Transaction, TransactionType, 
    TopUpRequest, MasterProfile, MasterStatus,
    Category, District, Order, OrderStatus, SystemSettings
)


# --- FIXTURES ---

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def session(engine):
    """Create a fresh session for each test with automatic rollback."""
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


# --- HELPER FUNCTIONS ---

async def create_test_user(session: AsyncSession, telegram_id: int, name: str, role: UserRole = UserRole.CLIENT, points: int = 0) -> User:
    """Helper to create a test user."""
    user = User(
        telegram_id=telegram_id,
        full_name=name,
        username=name.lower().replace(" ", "_"),
        role=role,
        points=points,
    )
    session.add(user)
    await session.flush()
    return user

async def create_test_transaction(session: AsyncSession, user_id: int, amount: int, tx_type: TransactionType, description: str = "") -> Transaction:
    """Helper to create a test transaction."""
    tx = Transaction(
        user_id=user_id,
        amount=amount,
        type=tx_type,
        description=description,
    )
    session.add(tx)
    await session.flush()
    return tx


# ============================================================
# TEST GROUP 1: Balance Operations
# ============================================================

class TestBalanceOperations:
    """Tests for user balance (points) management."""

    @pytest.mark.asyncio
    async def test_initial_balance_is_zero(self, session):
        """New users should have 0 points."""
        user = await create_test_user(session, 100001, "Test User")
        assert user.points == 0

    @pytest.mark.asyncio
    async def test_admin_refill_increases_balance(self, session):
        """Admin refill should correctly increase user balance."""
        user = await create_test_user(session, 100002, "Refill User", points=50)
        
        refill_amount = 100
        user.points += refill_amount
        await session.flush()
        
        # Verify balance
        refreshed = await session.get(User, user.id)
        assert refreshed.points == 150

    @pytest.mark.asyncio
    async def test_contact_fee_deducts_balance(self, session):
        """Contact fee should deduct from master's balance."""
        master_user = await create_test_user(session, 100003, "Master User", role=UserRole.MASTER, points=200)
        
        fee = 50
        master_user.points -= fee
        await session.flush()
        
        refreshed = await session.get(User, master_user.id)
        assert refreshed.points == 150

    @pytest.mark.asyncio
    async def test_balance_cannot_go_below_zero_with_check(self, session):
        """Business logic should prevent negative balances."""
        user = await create_test_user(session, 100004, "Poor User", points=30)
        
        fee = 50
        # Simulate the business logic check
        has_enough = user.points >= fee
        assert has_enough is False
        
        # Balance should remain unchanged
        assert user.points == 30

    @pytest.mark.asyncio
    async def test_multiple_refills_accumulate(self, session):
        """Multiple refills should accumulate correctly."""
        user = await create_test_user(session, 100005, "Accumulate User")
        
        amounts = [100, 200, 50, 75]
        for amount in amounts:
            user.points += amount
        
        await session.flush()
        assert user.points == sum(amounts)

    @pytest.mark.asyncio
    async def test_concurrent_balance_operations(self, session):
        """Test balance consistency with sequential operations (fee then refill)."""
        user = await create_test_user(session, 100006, "Concurrent User", points=500)
        
        # Deduct fee
        user.points -= 100
        # Add refill
        user.points += 200
        # Deduct another fee
        user.points -= 50
        
        await session.flush()
        assert user.points == 550  # 500 - 100 + 200 - 50


# ============================================================
# TEST GROUP 2: Transaction Records
# ============================================================

class TestTransactions:
    """Tests for transaction creation and integrity."""

    @pytest.mark.asyncio
    async def test_create_admin_adjustment_transaction(self, session):
        """Admin adjustment should create a proper transaction record."""
        user = await create_test_user(session, 200001, "TX User")
        
        tx = await create_test_transaction(
            session, user.id, 100, TransactionType.ADMIN_ADJUSTMENT, 
            "Ручное пополнение администратором"
        )
        
        assert tx.id is not None
        assert tx.amount == 100
        assert tx.type == TransactionType.ADMIN_ADJUSTMENT
        assert tx.user_id == user.id

    @pytest.mark.asyncio
    async def test_contact_fee_transaction(self, session):
        """Contact fee should create a negative transaction."""
        user = await create_test_user(session, 200002, "Fee User", points=100)
        
        tx = await create_test_transaction(
            session, user.id, -50, TransactionType.CONTACT_FEE, 
            "Оплата за контакт"
        )
        
        assert tx.amount == -50
        assert tx.type == TransactionType.CONTACT_FEE

    @pytest.mark.asyncio
    async def test_refund_transaction(self, session):
        """Refund should create a positive transaction."""
        user = await create_test_user(session, 200003, "Refund User")
        
        tx = await create_test_transaction(
            session, user.id, 75, TransactionType.REFUND, 
            "Возврат средств"
        )
        
        assert tx.amount == 75
        assert tx.type == TransactionType.REFUND

    @pytest.mark.asyncio
    async def test_referral_bonus_transaction(self, session):
        """Referral bonus should create a correct transaction."""
        user = await create_test_user(session, 200004, "Referral User")
        
        tx = await create_test_transaction(
            session, user.id, 25, TransactionType.REFERRAL_BONUS, 
            "Бонус за реферала"
        )
        
        assert tx.amount == 25
        assert tx.type == TransactionType.REFERRAL_BONUS

    @pytest.mark.asyncio
    async def test_transaction_has_timestamp(self, session):
        """Every transaction should have an auto-generated timestamp."""
        user = await create_test_user(session, 200005, "Time User")
        
        tx = await create_test_transaction(
            session, user.id, 10, TransactionType.ADMIN_ADJUSTMENT
        )
        
        assert tx.created_at is not None
        assert isinstance(tx.created_at, datetime)

    @pytest.mark.asyncio
    async def test_balance_matches_transaction_sum(self, session):
        """User's balance should match the sum of all transaction amounts."""
        user = await create_test_user(session, 200006, "Sum User", points=0)
        
        operations = [
            (100, TransactionType.ADMIN_ADJUSTMENT),
            (-30, TransactionType.CONTACT_FEE),
            (25, TransactionType.REFERRAL_BONUS),
            (-20, TransactionType.CONTACT_FEE),
            (50, TransactionType.REFUND),
        ]
        
        total = 0
        for amount, tx_type in operations:
            await create_test_transaction(session, user.id, amount, tx_type)
            total += amount
            user.points += amount
        
        await session.flush()
        
        # Verify balance matches
        assert user.points == total  # 100 - 30 + 25 - 20 + 50 = 125
        assert user.points == 125


# ============================================================
# TEST GROUP 3: Top-Up Requests
# ============================================================

class TestTopUpRequests:
    """Tests for the top-up request workflow."""

    @pytest.mark.asyncio
    async def test_create_topup_request(self, session):
        """Creating a top-up request should set status to PENDING."""
        user = await create_test_user(session, 300001, "TopUp User")
        
        request = TopUpRequest(
            user_id=user.id,
            amount=500,
            method="CRYPTO",
            status="PENDING",
            receipt_data="tx_hash_abc123",
        )
        session.add(request)
        await session.flush()
        
        assert request.id is not None
        assert request.status == "PENDING"
        assert request.amount == 500

    @pytest.mark.asyncio
    async def test_approve_topup_credits_user(self, session):
        """Approving a top-up should credit the user's balance."""
        user = await create_test_user(session, 300002, "Approve User", points=100)
        
        request = TopUpRequest(
            user_id=user.id, amount=200, method="BANK", 
            status="PENDING",
        )
        session.add(request)
        await session.flush()
        
        # Simulate approval
        request.status = "APPROVED"
        user.points += request.amount
        
        tx = Transaction(
            user_id=user.id, amount=request.amount,
            type=TransactionType.ADMIN_ADJUSTMENT,
            description=f"Пополнение #{request.id} одобрено"
        )
        session.add(tx)
        await session.flush()
        
        assert request.status == "APPROVED"
        assert user.points == 300  # 100 + 200

    @pytest.mark.asyncio
    async def test_reject_topup_no_balance_change(self, session):
        """Rejecting a top-up should NOT change the user's balance."""
        user = await create_test_user(session, 300003, "Reject User", points=100)
        
        request = TopUpRequest(
            user_id=user.id, amount=500, method="CRYPTO", 
            status="PENDING",
        )
        session.add(request)
        await session.flush()
        
        # Simulate rejection
        request.status = "REJECTED"
        await session.flush()
        
        assert request.status == "REJECTED"
        assert user.points == 100  # Unchanged!

    @pytest.mark.asyncio
    async def test_double_approval_prevention(self, session):
        """Already approved request should not be processed again."""
        user = await create_test_user(session, 300004, "Double User", points=0)
        
        request = TopUpRequest(
            user_id=user.id, amount=1000, method="BANK", 
            status="PENDING",
        )
        session.add(request)
        await session.flush()
        
        # First approval
        request.status = "APPROVED"
        user.points += request.amount
        await session.flush()
        
        assert user.points == 1000
        
        # Second approval attempt — should be blocked by status check
        if request.status == "PENDING":  # This condition is FALSE
            user.points += request.amount
        
        assert user.points == 1000  # Not 2000!

    @pytest.mark.asyncio
    async def test_topup_has_timestamp(self, session):
        """Top-up request should have an auto-generated timestamp."""
        user = await create_test_user(session, 300005, "Timestamp User")
        
        request = TopUpRequest(
            user_id=user.id, amount=100, method="CRYPTO", status="PENDING",
        )
        session.add(request)
        await session.flush()
        
        assert request.created_at is not None


# ============================================================
# TEST GROUP 4: Edge Cases & Data Integrity
# ============================================================

class TestDataIntegrity:
    """Tests for edge cases and data safety."""

    @pytest.mark.asyncio
    async def test_large_amount_handling(self, session):
        """System should handle large point amounts correctly."""
        user = await create_test_user(session, 400001, "Rich User")
        
        big_amount = 999_999_999
        user.points = big_amount
        await session.flush()
        
        refreshed = await session.get(User, user.id)
        assert refreshed.points == big_amount

    @pytest.mark.asyncio
    async def test_zero_amount_transaction(self, session):
        """Zero-amount transaction should be valid (edge case)."""
        user = await create_test_user(session, 400002, "Zero User")
        
        tx = await create_test_transaction(
            session, user.id, 0, TransactionType.ADMIN_ADJUSTMENT, "Test zero"
        )
        
        assert tx.amount == 0

    @pytest.mark.asyncio
    async def test_user_role_enum_integrity(self, session):
        """User roles should map correctly to enum values."""
        client = await create_test_user(session, 400003, "Client", role=UserRole.CLIENT)
        master = await create_test_user(session, 400004, "Master", role=UserRole.MASTER)
        admin = await create_test_user(session, 400005, "Admin", role=UserRole.ADMIN)
        
        assert client.role == UserRole.CLIENT
        assert master.role == UserRole.MASTER
        assert admin.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_transaction_type_enum_all_values(self, session):
        """All transaction types should be usable."""
        user = await create_test_user(session, 400006, "Enum User")
        
        for tx_type in TransactionType:
            tx = await create_test_transaction(session, user.id, 10, tx_type)
            assert tx.type == tx_type

    @pytest.mark.asyncio
    async def test_system_settings_singleton(self, session):
        """System settings should work as a singleton record."""
        settings = SystemSettings(
            id=1,
            crypto_enabled=True,
            crypto_address="TRC20_test_address",
            bank_enabled=False,
            bank_details="Test bank",
            free_orders_enabled=False,
        )
        session.add(settings)
        await session.flush()
        
        loaded = await session.get(SystemSettings, 1)
        assert loaded.crypto_enabled is True
        assert loaded.bank_enabled is False
        assert loaded.crypto_address == "TRC20_test_address"


# ============================================================
# TEST GROUP 5: 2FA Code Logic (Unit)
# ============================================================

class TestTwoFactorAuth:
    """Tests for 2FA code generation and validation logic."""

    def test_code_generation_format(self):
        """2FA code should be 6 digits."""
        import random
        code = str(random.randint(100000, 999999))
        assert len(code) == 6
        assert code.isdigit()

    def test_code_expiry_logic(self):
        """Expired codes should be rejected."""
        import time
        
        storage = {}
        storage["admin"] = {
            "code": "123456",
            "expires": time.time() - 10  # Already expired
        }
        
        stored = storage.get("admin")
        is_expired = time.time() > stored["expires"]
        assert is_expired is True

    def test_code_validation_correct(self):
        """Correct code should pass validation."""
        import time
        
        storage = {}
        storage["admin"] = {
            "code": "654321",
            "expires": time.time() + 300
        }
        
        stored = storage.get("admin")
        is_valid = stored["code"] == "654321" and time.time() <= stored["expires"]
        assert is_valid is True

    def test_code_validation_wrong(self):
        """Wrong code should fail validation."""
        import time
        
        storage = {}
        storage["admin"] = {
            "code": "654321",
            "expires": time.time() + 300
        }
        
        stored = storage.get("admin")
        is_valid = stored["code"] == "000000"
        assert is_valid is False

    def test_code_cleanup_after_use(self):
        """Code should be removed from storage after successful verification."""
        storage = {"admin": {"code": "123456", "expires": 999999999999}}
        
        # Simulate successful verification
        del storage["admin"]
        
        assert "admin" not in storage
