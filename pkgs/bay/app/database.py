from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
from typing import Optional, List
from app.config import settings
from app.models import Ship
from datetime import datetime, timezone


class DatabaseService:
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None

    async def initialize(self):
        """Initialize database connection"""
        self.engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
            # SQLite specific settings
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

    async def create_tables(self):
        """Create database tables"""
        if not self.engine:
            await self.initialize()

        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.engine:
            raise RuntimeError("Database not initialized")

        return AsyncSession(self.engine, expire_on_commit=False)

    async def create_ship(self, ship: Ship) -> Ship:
        """Create a new ship record"""
        session = self.get_session()
        try:
            session.add(ship)
            await session.commit()
            await session.refresh(ship)
            return ship
        finally:
            await session.close()

    async def get_ship(self, ship_id: str) -> Optional[Ship]:
        """Get ship by ID"""
        session = self.get_session()
        try:
            statement = select(Ship).where(Ship.id == ship_id)
            result = await session.exec(statement)
            return result.first()
        finally:
            await session.close()

    async def update_ship(self, ship: Ship) -> Ship:
        """Update ship record"""
        ship.updated_at = datetime.now(timezone.utc)
        session = self.get_session()
        try:
            session.add(ship)
            await session.commit()
            await session.refresh(ship)
            return ship
        finally:
            await session.close()

    async def delete_ship(self, ship_id: str) -> bool:
        """Delete ship by ID"""
        session = self.get_session()
        try:
            statement = select(Ship).where(Ship.id == ship_id)
            result = await session.exec(statement)
            ship = result.first()

            if ship:
                await session.delete(ship)
                await session.commit()
                return True
            return False
        finally:
            await session.close()

    async def list_active_ships(self) -> List[Ship]:
        """List all active ships"""
        session = self.get_session()
        try:
            statement = select(Ship).where(Ship.status == 1)
            result = await session.exec(statement)
            return result.all()
        finally:
            await session.close()

    async def count_active_ships(self) -> int:
        """Count active ships"""
        ships = await self.list_active_ships()
        return len(ships)


# Global database service instance
db_service = DatabaseService()
