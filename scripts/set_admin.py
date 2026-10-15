import asyncio
from sqlalchemy import select
from database.engine import async_session_maker
from database.models import User, UserRole
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def set_admin_password(username, password, role="superadmin"):
    async with async_session_maker() as session:
        stmt = select(User).where(User.username == username)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            print(f"User {username} not found. Creating a new admin...")
            user = User(
                telegram_id=0, # Dummy ID for manual admin
                full_name="Administrator",
                username=username,
                role=UserRole.ADMIN
            )
            session.add(user)
        
        user.hashed_password = pwd_context.hash(password)
        user.role = UserRole.ADMIN
        user.admin_role = role
        await session.commit()
        print(f"Successfully set password for admin: {username} (role: {role})")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python set_admin.py <username> <password> [superadmin|moderator|finance]")
    else:
        role = sys.argv[3] if len(sys.argv) > 3 else "superadmin"
        if role not in ("superadmin", "moderator", "finance"):
            raise SystemExit("role must be superadmin, moderator or finance")
        asyncio.run(set_admin_password(sys.argv[1], sys.argv[2], role))