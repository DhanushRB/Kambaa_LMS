import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

# Parse database URL
db_url = os.getenv("DATABASE_URL")
# mysql+pymysql://root:@localhost:3306/database
# We need root, host, and db name

try:
    # Very basic parsing for this specific format
    # Example: mysql+pymysql://root:@localhost:3306/database
    parts = db_url.split("://")[1].split("@")
    user_pass = parts[0].split(":")
    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ""
    
    host_port_db = parts[1].split("/")
    host_port = host_port_db[0].split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 3306
    db_name = host_port_db[1]

    # Connect to MySQL
    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=db_name,
        port=port
    )

    with connection.cursor() as cursor:
        # Check if column exists
        cursor.execute("DESCRIBE users")
        columns = [row[0] for row in cursor.fetchall()]
        
        if "github_link" not in columns:
            print("Adding github_link column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN github_link VARCHAR(500) NULL")
            connection.commit()
            print("Column added successfully.")
        else:
            print("github_link column already exists.")

except Exception as e:
    print(f"Error updating database: {e}")
finally:
    if 'connection' in locals():
        connection.close()
