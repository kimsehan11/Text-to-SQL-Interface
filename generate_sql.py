def generate_sql(question, schema_text):
    from build_prompt import build_prompt
    from llm import call_llm

    prompt = build_prompt(question, schema_text)
    sql_query = call_llm(prompt)

    return sql_query