import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def setup_new_database():
    old_url = os.getenv("DATABASE_URL")
    if not old_url:
        print("DATABASE_URL not found in .env")
        return

    # mysql+pymysql://root:@127.0.0.1:3306/tyre_shop
    parts = old_url.split("://")[1].split("/")
    auth_host = parts[0]
    
    auth_parts = auth_host.split("@")
    user_pass = auth_parts[0].split(":")
    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ""
    host_port = auth_parts[1].split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 3306
    
    db_name = "sanitary_store"
    new_url = f"mysql+pymysql://{auth_host}/{db_name}"

    try:
        # Create database
        conn = pymysql.connect(host=host, user=user, password=password, port=port)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        conn.close()
        print(f"Database {db_name} created successfully.")
    except Exception as e:
        print(f"Error creating database: {e}")
        return

    # Update .env
    try:
        with open(".env", "r") as f:
            lines = f.readlines()
        
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith("DATABASE_URL="):
                    f.write(f"DATABASE_URL={new_url}\n")
                else:
                    f.write(line)
        print("Updated .env with new DATABASE_URL")
    except Exception as e:
        print(f"Error updating .env: {e}")

if __name__ == "__main__":
    setup_new_database()
