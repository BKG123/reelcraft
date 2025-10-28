"""
Migration script to add storage_location field to videos table.

This script:
1. Adds the storage_location column to the videos table
2. Sets storage_location based on file_path (cloud URL vs local path)
"""

import asyncio
import sqlite3
from pathlib import Path


async def migrate():
    """Add storage_location column and populate it."""
    db_path = Path.cwd() / "reelcraft.db"

    if not db_path.exists():
        print("Database not found. Creating new database with updated schema.")
        from services.database import init_db
        await init_db()
        print("Database created successfully with storage_location field.")
        return

    print(f"Migrating database at: {db_path}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if storage_location column already exists
        cursor.execute("PRAGMA table_info(videos)")
        columns = [col[1] for col in cursor.fetchall()]

        if "storage_location" in columns:
            print("storage_location column already exists. Skipping migration.")
            return

        print("Adding storage_location column...")

        # Add the new column with default value 'LOCAL'
        cursor.execute("""
            ALTER TABLE videos
            ADD COLUMN storage_location TEXT NOT NULL DEFAULT 'LOCAL'
        """)

        # Update existing records: set to 'CLOUD' if file_path starts with http
        cursor.execute("""
            UPDATE videos
            SET storage_location = 'CLOUD'
            WHERE file_path LIKE 'http://%' OR file_path LIKE 'https://%'
        """)

        affected_rows = cursor.rowcount

        conn.commit()
        print(f"Migration completed successfully!")
        print(f"Updated {affected_rows} videos to cloud storage location.")

        # Show summary
        cursor.execute("SELECT storage_location, COUNT(*) FROM videos GROUP BY storage_location")
        summary = cursor.fetchall()
        print("\nStorage location summary:")
        for location, count in summary:
            print(f"  {location}: {count} videos")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
