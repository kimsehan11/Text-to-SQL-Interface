import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from langchain_openai import ChatOpenAI
# ── 설정 ──────────────────────────────────────────────────────────────────────
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
HF_REPO    = "your-hf-username/qwen2.5-text-to-sql"  # train.py와 동일하게 변경

_tokenizer = None
_model     = None

# ── 모델 로드 (최초 1회만) ─────────────────────────────────────────────────────
def _load_model():
    global _tokenizer, _model

    if _model is not None:
        return

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
  

# ── 추론 ──────────────────────────────────────────────────────────────────────
def call_hug_llm(prompt: str) -> str:
    _load_model()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a MySQL expert. "
                "Convert the user's natural language question into a valid MySQL SELECT query. "
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

    with torch.no_grad():
        output_ids = _model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            temperature=None,
            top_p=None,
            eos_token_id=_tokenizer.eos_token_id,
            pad_token_id=_tokenizer.eos_token_id,
        )

    generated = output_ids[0][inputs["input_ids"].shape[-1]:]
    return _tokenizer.decode(generated, skip_special_tokens=True).strip()

def call_openai_llm(prompt: str) -> str:
    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=0,
        max_tokens=256,
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a MySQL expert. "
                "Convert the user's natural language question into a valid MySQL SELECT query. "
                "Return only the SQL query."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    response = llm.invoke(messages)
    return response.content.strip()

def call_llm(prompt: str,hug=False) -> str:
    if hug:
        return call_hug_llm(prompt)
    return call_openai_llm(prompt)
