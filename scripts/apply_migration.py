import sys
import psycopg2
from urllib.parse import urlparse

def apply_migration(db_url, sql_file):
    print(f"Applying migration from {sql_file} to {db_url}...")
    
    try:
        # Parse connection URL
        result = urlparse(db_url)
        username = result.username
        password = result.password
        database = result.path[1:]
        hostname = result.hostname
        port = result.port or 5432

        # Connect to the database
        conn = psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Read SQL file
        with open(sql_file, 'r') as f:
            sql = f.read()

        # Execute SQL
        cur.execute(sql)
        
        print("Migration applied successfully.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error applying migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python apply_migration.py <db_url> <sql_file>")
        sys.exit(1)
    
    apply_migration(sys.argv[1], sys.argv[2])
