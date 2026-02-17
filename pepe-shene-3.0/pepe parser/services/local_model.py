from __future__ import annotations

import os
from pathlib import Path


class LocalWarehouseModel:
    """
    Minimal adapter for a local HuggingFace-compatible model.

    Required:
    - Set LOCAL_MODEL_PATH to directory of downloaded model.
    - Install transformers + torch.
    """

    def __init__(self) -> None:
        model_path = os.getenv("LOCAL_MODEL_PATH", "").strip()
        if not model_path:
            raise RuntimeError("LOCAL_MODEL_PATH is not set")

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise RuntimeError(f"Model path does not exist: {self.model_path}")

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
        except Exception as exc:
            raise RuntimeError("Install transformers and torch before using local model") from exc

        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path), use_fast=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path),
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
        )

    def generate(self, prompt: str) -> str:
        import torch

        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=3072)
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=220,
                do_sample=False,
                temperature=0.0,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        text = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return text[len(prompt):].strip() if text.startswith(prompt) else text.strip()
