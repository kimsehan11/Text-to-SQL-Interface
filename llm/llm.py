from openai import OpenAI

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
HF_REPO = "your-hf-username/qwen2.5-text-to-sql"
OPENAI_MODEL = "gpt-5.5"
_tokenizer = None
_model = None
_torch = None


def _load_model():
    global _tokenizer, _model, _torch

    if _model is not None:
        return

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    _torch = torch
    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    _tokenizer.pad_token = _tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    _model = PeftModel.from_pretrained(base, HF_REPO)
    _model.eval()


def call_hug_llm(prompt: str) -> str:
    _load_model()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a SQL expert. "
                "Convert the user's natural language question into a valid SELECT query. "
                "Return only the SQL query."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    text = _tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = _tokenizer(text, return_tensors="pt").to(_model.device)

    with _torch.no_grad():
        output_ids = _model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,
            temperature=None,
            top_p=None,
            eos_token_id=_tokenizer.eos_token_id,
            pad_token_id=_tokenizer.eos_token_id,
        )

    generated = output_ids[0][inputs["input_ids"].shape[-1]:]
    return _tokenizer.decode(generated, skip_special_tokens=True).strip()


def call_openai_llm(prompt: str) -> str:
    client = OpenAI()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a SQL expert. "
                    "Convert the user's natural language question into a valid SELECT query. "
                    "Return only the SQL query."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=2048,
    )

    return response.choices[0].message.content.strip()


def call_llm(prompt: str, hug=False) -> str:
    if hug:
        return call_hug_llm(prompt)
    return call_openai_llm(prompt)

