
from sqlalchemy import text

from app.db.session import engine

with engine.connect() as connection:
    result = connection.execute(text("SELECT current_database(), current_user"))
    database, user = result.fetchone()

    print(f"Database: {database}")
    print(f"User: {user}")
    print("Database connection successful!")
