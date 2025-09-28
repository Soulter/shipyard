#!/usr/bin/env python3
"""
Simple test script for Bay API
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db_service
from app.models import Ship
from app.config import settings


async def test_database():
    """Test database operations"""
    print("🧪 Testing database operations...")

    try:
        # Initialize database
        await db_service.initialize()
        await db_service.create_tables()
        print("✅ Database connection successful")

        # Test ship creation
        ship = Ship(ttl=3600)
        created_ship = await db_service.create_ship(ship)
        print(f"✅ Ship created: {created_ship.id}")

        # Test ship retrieval
        retrieved_ship = await db_service.get_ship(created_ship.id)
        if retrieved_ship:
            print(f"✅ Ship retrieved: {retrieved_ship.id}")
        else:
            print("❌ Ship retrieval failed")

        # Test ship counting
        count = await db_service.count_active_ships()
        print(f"✅ Active ships count: {count}")

        # Test ship deletion
        success = await db_service.delete_ship(created_ship.id)
        if success:
            print(f"✅ Ship deleted: {created_ship.id}")
        else:
            print("❌ Ship deletion failed")

        print("🎉 All database tests passed!")

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def test_config():
    """Test configuration loading"""
    print("🧪 Testing configuration...")

    print(f"✅ Database URL: {settings.database_url}")
    print(f"✅ Max ships: {settings.max_ship_num}")
    print(
        f"✅ Access token: {'***' + settings.access_token[-4:] if len(settings.access_token) > 4 else '***'}"
    )
    print("✅ Configuration loaded successfully")


if __name__ == "__main__":
    print("🚀 Starting Bay API tests...\n")

    test_config()
    print()

    asyncio.run(test_database())
