import os
from sqlalchemy import text
from app.database import engine

try:
    with engine.connect() as conn:
        # Check if we have 'size' column
        result = conn.execute(text("SHOW COLUMNS FROM items LIKE 'size'")).fetchone()
        if result:
            print("Migrating items table...")
            
            # Add new columns
            conn.execute(text("ALTER TABLE items ADD COLUMN name VARCHAR(150) AFTER brand"))
            conn.execute(text("ALTER TABLE items ADD COLUMN barcode VARCHAR(50) AFTER name"))
            conn.execute(text("ALTER TABLE items ADD COLUMN description TEXT AFTER category"))
            conn.execute(text("ALTER TABLE items ADD COLUMN supplier_id INTEGER AFTER description"))
            
            # Copy data
            conn.execute(text("UPDATE items SET name = CONCAT(IFNULL(brand, ''), ' ', IFNULL(size, ''), ' ', IFNULL(pattern, '')) WHERE name IS NULL"))
            conn.execute(text("UPDATE items SET description = CONCAT('Type: ', IFNULL(type, '')) WHERE description IS NULL"))
            
            # Drop old columns
            conn.execute(text("ALTER TABLE items DROP COLUMN size"))
            conn.execute(text("ALTER TABLE items DROP COLUMN pattern"))
            conn.execute(text("ALTER TABLE items DROP COLUMN type"))
            
            conn.commit()
            print("Migration successful.")
        else:
            print("Migration already applied or items table doesn't have old columns.")
except Exception as e:
    print(f"Error during migration: {e}")
