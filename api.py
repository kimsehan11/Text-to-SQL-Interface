import os
import re
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy import URL, create_engine, text

from db.extract_schema import extract_schema
from db.format_schema import format_schema
from llm.generate_sql import generate_sql

load_dotenv()

app = FastAPI(title="Text-to-SQL Interface")
CODE_VERSION = "sqlite-domain-retry-20260626-2"


class GenerateSqlRequest(BaseModel):
    question: str


class GenerateSqlResponse(BaseModel):
    sql: str = ""
    error: str = ""


class QueryRequest(BaseModel):
    question: str
    max_rows: int = 50


class QueryRow(BaseModel):
    values: list[str]


class QueryResponse(BaseModel):
    sql: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[QueryRow] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error: str = ""


@lru_cache(maxsize=1)
def get_engine():
    driver = os.getenv("DB_DRIVER", "mysql").strip().lower()

    if driver == "sqlite":
        sqlite_path = os.getenv("SQLITE_PATH", "").strip()
        if not sqlite_path:
            raise RuntimeError("SQLITE_PATH is required when DB_DRIVER=sqlite.")

        database_path = Path(sqlite_path).expanduser().resolve()
        if not database_path.exists():
            raise RuntimeError(f"SQLite database file does not exist: {database_path}")

        return create_engine(f"sqlite:///{database_path.as_posix()}", pool_pre_ping=True)

    database_url = URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME"),
    )

    return create_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_schema_text() -> str:
    schema = extract_schema(get_engine())
    dialect = os.getenv("DB_DRIVER", "mysql").strip().lower()

    if dialect == "sqlite":
        return (
            f"SQL dialect: {dialect}\n\n"
            + get_sqlite_export_notes()
            + "\n\nPhysical SQLite tables:\n"
            + format_schema(schema)
        )

    return f"SQL dialect: {dialect}\n\n" + format_schema(schema)


def get_sqlite_export_notes() -> str:
    try:
        with get_engine().connect() as connection:
            source_tables = connection.execute(text("""
                SELECT name, domain, source_path
                FROM source_tables
                ORDER BY name
            """)).fetchall()

            table_columns = connection.execute(text("""
                SELECT table_name, column_name
                FROM table_columns
                ORDER BY table_name, column_index
            """)).fetchall()
    except Exception as exception:
        return f"SQLite export notes unavailable: {exception}"

    columns_by_table: dict[str, list[str]] = {}
    for table_name, column_name in table_columns:
        columns_by_table.setdefault(table_name, []).append(column_name)

    lines = [
        "Important SQLite export layout:",
        "Game balance CSV/JSON exports are stored as logical tables, but each logical table is NOT a physical SQLite table.",
        "Physical tables table_columns, table_rows, and table_cells describe and store all logical table data.",
        "Use source_tables and table_columns only as metadata to identify the logical table and columns that match the user question.",
        "Do not answer user data questions by selecting from source_tables or table_columns unless the user explicitly asks for metadata or a list of available tables.",
        "For game data questions, always query table_cells, filter table_cells.table_name to the chosen logical table, and pivot rows with CASE expressions grouped by row_index.",
        "Use number_value for numeric cells, string_value for text cells, and bool_value for boolean cells.",
        "Examples:",
        "User asks: 몹들이 주는 경험치 보상 목록을 보여줘",
        "Use logical table: MobExperience; columns: MobName, Experience",
        "User asks: 스테이지 클리어 보상 경험치를 보여줘",
        "Use logical table: StageExperience; columns: StageName, Experience",
        "User asks: 플레이어 레벨업에 필요한 누적 경험치를 보여줘",
        "Use logical table: PlayerLevelExperience; columns: Level, Cumulative_Experience",
        "",
        "Generic pivot pattern:",
        "SELECT row_index,",
        "       MAX(CASE WHEN column_name = '<ColumnName>' THEN COALESCE(CAST(number_value AS TEXT), string_value, CAST(bool_value AS TEXT)) END) AS '<ColumnName>'",
        "FROM table_cells",
        "WHERE table_name = '<LogicalTableName>'",
        "GROUP BY row_index",
        "ORDER BY row_index",
        "",
        "Korean domain hints for matching user words to logical source tables:",
        "- 몹, 몬스터, 적, enemy, monster, 경험치 보상, 처치 보상 usually refer to MobExperience.",
        "- 스테이지, stage, 클리어 보상, 완료 보상 usually refer to StageExperience.",
        "- 레벨 경험치, 레벨별 경험치, 필요 경험치 usually refer to LevelExperience.",
        "- 플레이어 레벨업, 플레이어 경험치, 누적 경험치 usually refer to PlayerLevelExperience.",
        "- 가챠 캐릭터, 캐릭터 뽑기, character gacha usually refer to GachaCharacters.",
        "- 무기 파츠, 파츠 가챠, weapon parts usually refer to GachaParts.",
        "- 방패 파츠, 실드 파츠, shield parts usually refer to GachaShieldParts.",
        "- 방패 가챠, 실드 가챠, shield gacha usually refer to GachaShields.",
        "- 완드, 지팡이, wand gacha usually refer to GachaWands.",
        "- 제작, 조합, 레시피, craft usually refer to CraftRecipes or CraftRecipeIngredients.",
        "- 드랍, drop, 아이템 드랍, 보상 가중치 usually refer to DropWeights.",
        "- 스폰, spawn, 적 등장, 몬스터 등장 usually refer to EnemySpawnWeights.",
        "When the user uses Korean domain words, infer the closest logical source table from these hints and the table/column names. Do not return CLARIFICATION_NEEDED if a close match exists.",
        "",
        "Logical source tables available to query:",
    ]

    for name, domain, source_path in source_tables:
        columns = ", ".join(columns_by_table.get(name, []))
        lines.append(f"- {name} ({domain}) from {source_path}; columns: {columns}")

    return "\n".join(lines)


def normalize_sql(sql: str) -> str:
    cleaned = sql.strip()
    cleaned = re.sub(r"^```(?:sql)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned.rstrip(";").strip()


def is_safe_select(sql: str) -> bool:
    lowered = sql.strip().lower()
    blocked = ("insert", "update", "delete", "drop", "alter", "create", "truncate", "replace")

    if ";" in lowered:
        return False

    return lowered.startswith("select") and not any(re.search(rf"\b{word}\b", lowered) for word in blocked)




def expected_logical_tables_for_question(question: str) -> list[str]:
    lowered = question.lower()
    expected: list[str] = []

    if any(word in lowered for word in ("가챠 캐릭터", "캐릭터 뽑기", "character gacha")):
        expected.append("GachaCharacters")
    elif any(word in lowered for word in ("무기 파츠", "파츠 가챠", "weapon parts")):
        expected.append("GachaParts")
    elif any(word in lowered for word in ("방패 파츠", "실드 파츠", "shield parts")):
        expected.append("GachaShieldParts")
    elif any(word in lowered for word in ("방패 가챠", "실드 가챠", "shield gacha")):
        expected.append("GachaShields")
    elif any(word in lowered for word in ("완드", "지팡이", "wand")):
        expected.append("GachaWands")
    elif any(word in lowered for word in ("가챠", "뽑기", "gacha")):
        expected.extend(["GachaCharacters", "GachaParts", "GachaShieldParts", "GachaShields", "GachaWands"])

    if any(word in lowered for word in ("드랍", "drop", "아이템 드랍", "보상 가중치")):
        expected.append("DropWeights")

    if any(word in lowered for word in ("스폰", "spawn", "적 등장", "몬스터 등장")):
        expected.append("EnemySpawnWeights")

    if any(word in lowered for word in ("몹 경험치", "몬스터 경험치", "처치 경험치", "경험치 보상", "몹들이 주는")):
        expected.append("MobExperience")

    if any(word in lowered for word in ("스테이지", "stage", "클리어 보상")):
        expected.append("StageExperience")

    if any(word in lowered for word in ("플레이어 레벨업", "플레이어 경험치", "누적 경험치")):
        expected.append("PlayerLevelExperience")

    if any(word in lowered for word in ("레벨 경험치", "레벨별 경험치", "필요 경험치")) and "플레이어" not in lowered:
        expected.append("LevelExperience")

    return list(dict.fromkeys(expected))


def extract_table_cell_names(sql: str) -> list[str]:
    return re.findall(r"table_name\s*=\s*['\"]([^'\"]+)['\"]", sql, flags=re.IGNORECASE)


def has_domain_mismatch(question: str, sql: str) -> bool:
    expected = expected_logical_tables_for_question(question)
    if not expected:
        return False

    actual = extract_table_cell_names(sql)
    if not actual:
        return True

    return not any(table_name in expected for table_name in actual)


def build_domain_retry_question(question: str, previous_sql: str) -> str:
    expected = ", ".join(expected_logical_tables_for_question(question))
    return f"""
The previous SQL chose the wrong logical source table for the original user question.

Original user question:
{question}

Expected logical source table candidates from the user's domain words:
{expected}

Previous SQL:
{previous_sql}

Generate a corrected SELECT query for the original user question.
Do not use MobExperience unless the question is specifically about enemy/mob experience rewards.
Use table_cells, filter table_name to one of the expected logical source table candidates, and pivot rows with CASE expressions grouped by row_index.
Return only the corrected SQL.
""".strip()
def is_metadata_listing_query(sql: str) -> bool:
    lowered = " ".join(sql.lower().split())
    metadata_tables = ("source_tables", "table_columns", "table_rows")

    if "table_cells" in lowered:
        return False

    return any(f"from {table}" in lowered for table in metadata_tables)


def build_retry_question(question: str, previous_sql: str) -> str:
    return f"""
The previous SQL only queried metadata instead of the actual game data:
{previous_sql}

The original user question was:
{question}

Generate a corrected SELECT query for the ORIGINAL user question.
Do not choose a table from an example unless it matches the original user's domain words.
For game data questions, do not answer from source_tables, table_columns, or table_rows.
Use those metadata tables only to decide the logical source table and columns.
Then query table_cells, filter table_name to the chosen logical source table, and pivot rows with CASE expressions grouped by row_index.

Domain matching requirements:
- If the original question mentions 가챠, 뽑기, character gacha, 캐릭터, use a Gacha* logical table, not MobExperience.
- If it mentions 가챠 캐릭터 or 캐릭터 뽑기, use GachaCharacters.
- If it mentions 무기 파츠 or 파츠 가챠, use GachaParts.
- If it mentions 드랍, drop, 아이템 드랍, or 보상 가중치, use DropWeights.
- If it mentions 스폰, spawn, 적 등장, or 몬스터 등장, use EnemySpawnWeights.
- If it mentions 몹 경험치, 몬스터 경험치, 처치 경험치, or 경험치 보상 from enemies, use MobExperience.
- If it mentions 스테이지 클리어 보상 or 스테이지 경험치, use StageExperience.
- If it mentions 플레이어 레벨업 or 누적 경험치, use PlayerLevelExperience.

Return only the corrected SQL.
""".strip()
def stringify_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    return str(value)


def build_sql(question: str) -> tuple[str, str]:
    if not question:
        return "", "Question is empty."

    schema_text = get_schema_text()

    try:
        sql = normalize_sql(generate_sql(question, schema_text))
        if is_metadata_listing_query(sql):
            retry_question = build_retry_question(question, sql)
            sql = normalize_sql(generate_sql(retry_question, schema_text))

        if has_domain_mismatch(question, sql):
            retry_question = build_domain_retry_question(question, sql)
            sql = normalize_sql(generate_sql(retry_question, schema_text))
    except Exception as exception:
        return "", f"Failed to generate SQL: {exception}"

    if sql == "CLARIFICATION_NEEDED":
        return "", "CLARIFICATION_NEEDED"

    if is_metadata_listing_query(sql):
        return "", "Generated query only listed metadata instead of querying table_cells."

    if has_domain_mismatch(question, sql):
        return "", "Generated query used the wrong logical source table for the question."

    if not is_safe_select(sql):
        return "", "Generated query was rejected because it is not a safe SELECT query."

    return sql, ""


def execute_select(sql: str, max_rows: int) -> tuple[list[str], list[QueryRow], bool]:
    safe_max_rows = max(1, min(max_rows, 200))

    with get_engine().connect() as connection:
        result = connection.execute(text(sql))
        columns = list(result.keys())
        fetched_rows = result.fetchmany(safe_max_rows + 1)

    visible_rows = fetched_rows[:safe_max_rows]
    rows = [
        QueryRow(values=[stringify_value(value) for value in row])
        for row in visible_rows
    ]

    return columns, rows, len(fetched_rows) > safe_max_rows


@app.get("/health")
def health():
    schema_text = get_schema_text()
    return {
        "ok": True,
        "code_version": CODE_VERSION,
        "db_driver": os.getenv("DB_DRIVER", "mysql").strip().lower(),
        "has_korean_hints": "Korean domain hints" in schema_text,
        "has_mob_experience": "MobExperience" in schema_text,
    }


@app.post("/generate-sql", response_model=GenerateSqlResponse)
def generate(request: GenerateSqlRequest):
    sql, error = build_sql(request.question.strip())
    if error:
        return GenerateSqlResponse(error=error)

    return GenerateSqlResponse(sql=sql)


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    sql, error = build_sql(request.question.strip())
    if error:
        return QueryResponse(error=error)

    try:
        columns, rows, truncated = execute_select(sql, request.max_rows)
    except Exception as exception:
        return QueryResponse(sql=sql, error=f"Failed to execute SQL: {exception}")

    return QueryResponse(
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )


@app.post("/debug/generate-sql", response_model=GenerateSqlResponse)
def debug_generate(request: GenerateSqlRequest):
    sql, error = build_sql(request.question.strip())
    return GenerateSqlResponse(sql=sql, error=error)




@app.post("/debug/raw-llm", response_model=GenerateSqlResponse)
def debug_raw_llm(request: GenerateSqlRequest):
    from llm.build_prompt import build_prompt
    from llm.llm import call_openai_llm

    prompt = build_prompt(request.question.strip(), get_schema_text())
    raw = call_openai_llm(prompt)
    return GenerateSqlResponse(sql=raw, error="")






@app.post("/debug/domain-check", response_model=dict)
def debug_domain_check(request: GenerateSqlRequest):
    sql, error = build_sql(request.question.strip())
    return {
        "question": request.question,
        "sql": sql,
        "error": error,
        "expected": expected_logical_tables_for_question(request.question),
        "actual": extract_table_cell_names(sql),
        "mismatch": has_domain_mismatch(request.question, sql),
    }
