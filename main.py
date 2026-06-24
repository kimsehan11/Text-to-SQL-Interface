import os
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from extract_schema import extract_schema, print_schema
from format_schema import format_schema
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

from extract_schema import extract_schema
from format_schema import format_schema
from build_prompt import build_prompt


schema = extract_schema()
schema_text = format_schema(schema)

question = "서울 고객들의 주문 내역을 보여줘"

prompt = build_prompt(
    question,
    schema_text
)

print(prompt)