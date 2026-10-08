from sqlalchemy import text

from app.core.database import engine


with engine.connect() as connection:
    result = connection.execute(
        text("SELECT current_database();")
    )

    database_name = result.scalar()

    print("Connected to PostgreSQL successfully!")
    print(f"Database: {database_name}")