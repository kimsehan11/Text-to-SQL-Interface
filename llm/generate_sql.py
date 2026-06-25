from llm.build_prompt import build_prompt
from llm.llm import call_llm

def generate_sql(question, schema_text):
    prompt = build_prompt(question, schema_text)
    sql_query = call_llm(prompt, hug=False)

    return sql_query