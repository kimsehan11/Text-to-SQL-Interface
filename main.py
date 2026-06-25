import os
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from db.extract_schema import extract_schema, print_schema
from db.format_schema import format_schema
from sqlalchemy.exc import SQLAlchemyError
from llm.llm import call_llm

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

from db.extract_schema import extract_schema
from db.format_schema import format_schema
from llm.build_prompt import build_prompt


schema = extract_schema(engine)
schema_text = format_schema(schema)

question = "서울 고객들의 주문 내역을 보여줘"

prompt = build_prompt(
    question,
    schema_text
)

print(call_llm(prompt, hug=False))