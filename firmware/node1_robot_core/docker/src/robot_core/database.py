"""
OpenJ5 Robot Core - Database Manager

SQLAlchemy async database manager with migrations.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text, event
from alembic.config import Config as AlembicConfig
from alembic import command

from robot_core.config import ConfigService
from robot_core.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Async database manager with connection pooling and migrations."""
    
    def __init__(self, config: ConfigService):
        self.config = config
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database engine and run migrations."""
        if self._initialized:
            return
        
        database_url = self.config.get("database.url")
        if not database_url:
            raise ValueError("Database URL not configured")
        
        # Create async engine
        self.engine = create_async_engine(
            database_url,
            pool_size=self.config.get("database.pool_size", 10),
            max_overflow=self.config.get("database.max_overflow", 20),
            pool_timeout=self.config.get("database.pool_timeout", 30),
            pool_recycle=self.config.get("database.pool_recycle", 3600),
            pool_pre_ping=True,
            echo=self.config.get("database.echo", False),
        )
        
        # Session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        
        # Run migrations
        await self._run_migrations()
        
        self._initialized = True
        logger.info("Database initialized", url=database_url)
    
    async def _run_migrations(self) -> None:
        """Run Alembic migrations if a migrations directory is present."""
        import importlib.resources

        script_location = Path("migrations")
        if not script_location.exists() and not importlib.resources.files("robot_core").joinpath("migrations").exists():
            logger.info("No migrations directory found, skipping migrations")
            return

        try:
            # Alembic config
            alembic_cfg = AlembicConfig()
            alembic_cfg.set_main_option("script_location", str(script_location))
            alembic_cfg.set_main_option("sqlalchemy.url", 
                self.config.get("database.url").replace("+asyncpg", ""))
            
            # Run in thread pool (Alembic is synchronous)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, command.upgrade, alembic_cfg, "head")
            
            logger.info("Database migrations completed")
        except Exception as e:
            logger.error("Migration failed", error=str(e))
            raise
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic commit/rollback."""
        if not self._initialized:
            await self.initialize()
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def execute(self, query: str, params: dict | None = None) -> Any:
        """Execute raw SQL query."""
        async with self.session() as session:
            result = await session.execute(text(query), params or {})
            return result
    
    async def fetch_one(self, query: str, params: dict | None = None) -> Optional[dict]:
        """Fetch single row as dict."""
        async with self.session() as session:
            result = await session.execute(text(query), params or {})
            row = result.fetchone()
            return dict(row._mapping) if row else None
    
    async def fetch_all(self, query: str, params: dict | None = None) -> list[dict]:
        """Fetch all rows as list of dicts."""
        async with self.session() as session:
            result = await session.execute(text(query), params or {})
            return [dict(row._mapping) for row in result.fetchall()]
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._initialized = False
            logger.info("Database connections closed")


async def get_database(config: ConfigService) -> DatabaseManager:
    """Get or create database manager."""
    db = DatabaseManager(config)
    await db.initialize()
    return db