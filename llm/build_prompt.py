def build_prompt(question, schema_text):
    prompt = """
You are a SQL expert.

Convert the user's natural language question into a valid SELECT query for the SQL dialect shown in the schema section.

Rules:
1. Use only physical tables and columns that exist in the schema.
2. Generate only SELECT queries.
3. Do not generate INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.
4. If the schema includes a logical export layout, infer the closest logical source table from the user's words, Korean domain hints, source table names, domains, source paths, and columns.
5. For logical export data, query the physical table_cells table and pivot rows with CASE expressions grouped by row_index.
6. When the user uses broad Korean game terms, choose the closest matching logical source table from the provided hints and table list.
7. If multiple tables are plausible, choose the most specific one and generate a useful SELECT query.
8. Return only the SQL query. Do not return explanations, comments, markdown, or placeholder queries.

Database schema:
"""

    prompt += schema_text

    prompt += "\nUser question:\n"
    prompt += question

    return prompt
