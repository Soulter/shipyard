#!/usr/bin/env python3
"""
Database initialization script for Bay API
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db_service


async def init_db():
    """Initialize database tables"""
    try:
        print("🔧 Initializing database...")
        await db_service.initialize()
        await db_service.create_tables()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_db())
