"""
Fix storage_location case in database (lowercase to uppercase).
"""

import sqlite3
from pathlib import Path


def fix_storage_case():
    """Convert storage_location values to uppercase."""
    db_path = Path.cwd() / "reelcraft.db"

    if not db_path.exists():
        print("Database not found.")
        return

    print(f"Fixing storage_location case in: {db_path}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Show current state
        cursor.execute("SELECT id, title, storage_location FROM videos")
        videos = cursor.fetchall()
        print("\nBefore fix:")
        for vid in videos:
            print(f"  [{vid[0]}] {vid[1]}: {vid[2]}")

        # Update to uppercase
        cursor.execute("UPDATE videos SET storage_location = 'LOCAL' WHERE storage_location = 'local'")
        local_updated = cursor.rowcount

        cursor.execute("UPDATE videos SET storage_location = 'CLOUD' WHERE storage_location = 'cloud'")
        cloud_updated = cursor.rowcount

        conn.commit()

        # Show updated state
        cursor.execute("SELECT id, title, storage_location FROM videos")
        videos = cursor.fetchall()
        print("\nAfter fix:")
        for vid in videos:
            print(f"  [{vid[0]}] {vid[1]}: {vid[2]}")

        print(f"\nUpdated {local_updated} LOCAL and {cloud_updated} CLOUD entries")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    fix_storage_case()
