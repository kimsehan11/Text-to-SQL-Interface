def build_prompt(question, schema_text):
    prompt = """
You are a MySQL expert.

Convert the user's natural language question into a valid MySQL SELECT query.

Rules:
1. Use only tables and columns that exist in the schema.
2. Generate only SELECT queries.
3. Do not generate INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.
4. Do not guess nonexistent values.
5. If the question is ambiguous, return CLARIFICATION_NEEDED.
6. Return only the SQL query.

Database schema:
"""

    prompt += schema_text

    prompt += "\nUser question:\n"
    prompt += question

    return prompt