def format_schema(schema):
    lines = []

    for table_name in schema:
        table_info = schema[table_name]

        lines.append("Table: " + table_name)

        for column in table_info["columns"]:
            line = "- " + column["name"] + ": " + column["type"]

            if column["name"] in table_info["primary_key"]:
                line += ", primary key"

            if column["nullable"] is False:
                line += ", not null"

            if "sample_values" in column:
                samples = ", ".join(
                    str(value)
                    for value in column["sample_values"]
                )

                line += ", sample values: " + samples

            lines.append(line)

        for foreign_key in table_info["foreign_keys"]:
            column_name = foreign_key["columns"][0]
            referred_column = foreign_key["referred_columns"][0]

            lines.append(
                "- foreign key: "
                + column_name
                + " -> "
                + foreign_key["referred_table"]
                + "."
                + referred_column
            )

        lines.append("")

    return "\n".join(lines)