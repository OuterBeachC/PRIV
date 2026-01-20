import sqlite3

def add_and_populate_source_identifier():
    conn = sqlite3.connect('priv_data.db')
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(financial_data)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'source_identifier' not in columns:
            print("Adding source_identifier column...")
            cursor.execute("ALTER TABLE financial_data ADD COLUMN source_identifier TEXT")
            print("✅ Column added successfully")
        else:
            print("source_identifier column already exists")
        
        # Check how many rows need updating
        cursor.execute("SELECT COUNT(*) FROM financial_data WHERE source_identifier IS NULL")
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"Updating {null_count} rows with default value...")
            cursor.execute("UPDATE financial_data SET source_identifier = 'PRIV' WHERE source_identifier IS NULL")
            print("✅ Existing rows updated")
        else:
            print("All rows already have source_identifier values")
        
        conn.commit()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_and_populate_source_identifier()