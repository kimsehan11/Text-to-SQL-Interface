import os
import torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer

# ── 설정 ──────────────────────────────────────────────────────────────────────
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
HF_REPO    = "your-hf-username/qwen2.5-text-to-sql"  # 본인 허깅페이스 레포로 변경
DATASET    = "b-mc2/sql-create-context"
OUTPUT_DIR = "../output"

LORA_CONFIG = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

TRAINING_ARGS = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    fp16=True,
    logging_steps=50,
    save_strategy="epoch",
    push_to_hub=True,
    hub_model_id=HF_REPO,
)

MAX_LENGTH = 512

# ── 프롬프트 포맷 ──────────────────────────────────────────────────────────────
def format_prompt(example):
    system = (
        "You are a MySQL expert. "
        "Convert the user's natural language question into a valid MySQL SELECT query. "
        "Return only the SQL query."
    )
    user = (
        f"Database schema:\n{example['context']}\n\n"
        f"User question:\n{example['question']}"
    )
    answer = example["answer"]

    return {
        "text": (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n{answer}<|im_end|>"
        )
    }

# ── 학습 ──────────────────────────────────────────────────────────────────────
def main():
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = get_peft_model(model, LORA_CONFIG)
    model.print_trainable_parameters()

    dataset = load_dataset(DATASET, split="train")
    dataset = dataset.map(format_prompt)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_LENGTH,
        args=TRAINING_ARGS,
    )

    trainer.train()
    trainer.push_to_hub()
    print(f"모델 업로드 완료: https://huggingface.co/{HF_REPO}")


if __name__ == "__main__":
    main()
