import os
from typing import Any
from sqlalchemy import  inspect, text

def get_sample_values(engine,table_name, column_name):
    query = text(
        f"""
        SELECT DISTINCT `{column_name}`
        FROM `{table_name}`
        WHERE `{column_name}` IS NOT NULL
        LIMIT 5
        """
    )

    with engine.connect() as connection:
        result = connection.execute(query)

        sample_values = []

        for row in result:
            sample_values.append(row[0])

    return sample_values

def is_categorical_column(engine, table_name, column_name):
    query = text(
        f"""
        SELECT COUNT(DISTINCT `{column_name}`)
        FROM `{table_name}`
        """
    )

    with engine.connect() as connection:
        result = connection.execute(query)
        distinct_count = result.scalar()

    return distinct_count <= 20

def extract_schema(engine):
    inspector = inspect(engine)
    schema = {}

    table_names = inspector.get_table_names()

    for table_name in table_names:
        columns = inspector.get_columns(table_name)
        primary_key = inspector.get_pk_constraint(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)

        column_list = []

        for column in columns:
            column_info = {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column["nullable"]
            }

            column_type = str(column["type"]).upper()

            if (
                "VARCHAR" in column_type
                or "CHAR" in column_type
                or "TEXT" in column_type
            ):
                if is_categorical_column(
                    engine,
                    table_name,
                    column["name"]
                ):
                    sample_values = get_sample_values(
                        engine,
                        table_name,
                        column["name"]
                    )

                    column_info["sample_values"] = sample_values

            column_list.append(column_info)

        foreign_key_list = []

        for foreign_key in foreign_keys:
            foreign_key_info = {
                "columns": foreign_key["constrained_columns"],
                "referred_table": foreign_key["referred_table"],
                "referred_columns": foreign_key["referred_columns"]
            }

            foreign_key_list.append(foreign_key_info)

        table_info = {
            "columns": column_list,
            "primary_key": primary_key.get("constrained_columns", []),
            "foreign_keys": foreign_key_list
        }

        schema[table_name] = table_info

    return schema

def print_schema(schema):
    for table_name in schema:
        table_info = schema[table_name]

        print()
        print("테이블:", table_name)

        print("컬럼:")

        for column in table_info["columns"]:
            print(
                "-",
                column["name"],
                column["type"],
                "nullable=",
                column["nullable"]
            )

            if "sample_values" in column:
                print(
                    "  샘플 값:",
                    column["sample_values"]
                )

        print("Primary Key:", table_info["primary_key"])

        print("Foreign Keys:")

        if len(table_info["foreign_keys"]) == 0:
            print("- 없음")
        else:
            for foreign_key in table_info["foreign_keys"]:
                print(
                    "-",
                    foreign_key["columns"],
                    "->",
                    foreign_key["referred_table"],
                    foreign_key["referred_columns"]
                )




