"""QLoRA fine-tuning of Qwen3-14B on the parser labels from lora/build_labels.py.

Runs on one GPU with >= 40 GB (Colab A100 / G4). Loss is on the assistant reply (the
parser JSON) only. The prompt is rendered with the model's chat template and
`enable_thinking=False`, exactly as vLLM renders it at inference.

    python lora/train_qlora.py --data labels.jsonl --out /content/lora-parse
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random

import torch
import transformers
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

_TF_MAJOR = int(transformers.__version__.split(".")[0])
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def load_examples(path: str, tokenizer, max_len: int) -> list[dict[str, list[int]]]:
    out = []
    skipped = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            messages = row["messages"]
            prompt = tokenizer.apply_chat_template(
                messages[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
            reply = messages[-1]["content"] + tokenizer.eos_token
            p_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            r_ids = tokenizer(reply, add_special_tokens=False)["input_ids"]
            if len(p_ids) + len(r_ids) > max_len:
                skipped += 1
                continue
            out.append(
                {"input_ids": p_ids + r_ids, "labels": [-100] * len(p_ids) + r_ids}
            )
    print(f"examples: {len(out)} (skipped {skipped} longer than {max_len} tokens)")
    return out


class Collator:
    def __init__(self, pad_id: int) -> None:
        self.pad_id = pad_id

    def __call__(self, batch: list[dict[str, list[int]]]) -> dict[str, torch.Tensor]:
        n = max(len(b["input_ids"]) for b in batch)
        ids = [b["input_ids"] + [self.pad_id] * (n - len(b["input_ids"])) for b in batch]
        labels = [b["labels"] + [-100] * (n - len(b["labels"])) for b in batch]
        mask = [[1] * len(b["input_ids"]) + [0] * (n - len(b["input_ids"])) for b in batch]
        return {
            "input_ids": torch.tensor(ids),
            "labels": torch.tensor(labels),
            "attention_mask": torch.tensor(mask),
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--base", default="Qwen/Qwen3-14B")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-len", type=int, default=2560)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    examples = load_examples(args.data, tokenizer, args.max_len)
    random.shuffle(examples)

    model = AutoModelForCausalLM.from_pretrained(
        args.base,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        ),
        device_map={"": 0},
        # transformers 5 renamed torch_dtype -> dtype
        **({"dtype": torch.bfloat16} if _TF_MAJOR >= 5 else {"torch_dtype": torch.bfloat16}),
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.rank,
            lora_alpha=args.alpha,
            lora_dropout=0.05,
            target_modules=TARGET_MODULES,
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    total_steps = math.ceil(len(examples) / args.grad_accum) * args.epochs
    warmup_steps = max(1, int(0.03 * total_steps))  # warmup_ratio is gone in transformers 5
    print(f"optimizer steps: ~{total_steps:.0f}, warmup: {warmup_steps}")
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=args.out + "-ckpt",
            per_device_train_batch_size=1,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            warmup_steps=warmup_steps,
            bf16=True,
            logging_steps=10,
            save_steps=50,
            save_total_limit=2,
            gradient_checkpointing=True,
            report_to=[],
            seed=args.seed,
        ),
        train_dataset=examples,
        data_collator=Collator(tokenizer.pad_token_id),
    )
    ckpt_dir = args.out + "-ckpt"
    has_ckpt = os.path.isdir(ckpt_dir) and any(d.startswith("checkpoint-") for d in os.listdir(ckpt_dir))
    trainer.train(resume_from_checkpoint=True if has_ckpt else None)  # Colab may disconnect
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    print("saved adapter ->", args.out)


if __name__ == "__main__":
    main()
