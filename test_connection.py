import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()

database_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
)


def test_connection() -> None:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT DATABASE();")
            )
            database_name = result.scalar()

            print("MySQL 연결 성공")
            print(f"현재 데이터베이스: {database_name}")

    except SQLAlchemyError as error:
        print(f"MySQL 연결 실패: {error}")


if __name__ == "__main__":
    test_connection()