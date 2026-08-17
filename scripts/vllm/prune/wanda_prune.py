#!/usr/bin/env python3
"""One-shot UNSTRUCTURED Wanda pruning via llmcompressor.

Loads a causal LM, calibrates llmcompressor's WandaPruningModifier on a
plain-text calibration dataset (C4 by default, WikiText-2 as an automatic
fallback), and saves the pruned checkpoint. This produces dense safetensors
with zeroed weights at the target sparsity - same file layout as the base
model, loadable by vLLM exactly like any other Hugging Face checkpoint. No
retraining/fine-tuning. No structured N:M mask (unstructured only, per
current scope) - see WandaPruningModifier(mask_structure=...) if that's
needed later.

Reference: "A Simple and Effective Pruning Approach for Large Language
Models" (Wanda), https://arxiv.org/abs/2306.11695
"""
from __future__ import annotations

import argparse
import sys


def build_calibration_dataset(tokenizer, name: str, num_samples: int, max_seq_length: int, seed: int):
    from datasets import Dataset, load_dataset

    def _from_c4():
        stream = load_dataset("allenai/c4", "en", split="train", streaming=True)
        stream = stream.shuffle(seed=seed, buffer_size=10_000)
        texts = []
        for example in stream:
            text = example.get("text", "")
            if text and len(text.strip()) > 100:
                texts.append(text)
            if len(texts) >= num_samples:
                break
        if len(texts) < num_samples:
            raise RuntimeError(f"only found {len(texts)}/{num_samples} usable C4 samples")
        return Dataset.from_list([{"text": t} for t in texts])

    def _from_wikitext2():
        raw = load_dataset("wikitext", "wikitext-2-raw-v1", split="train")
        raw = raw.shuffle(seed=seed)
        texts = [t for t in raw["text"] if len(t.strip()) > 100][:num_samples]
        if len(texts) < num_samples:
            raise RuntimeError(f"only found {len(texts)}/{num_samples} usable WikiText-2 samples")
        return Dataset.from_list([{"text": t} for t in texts])

    loaders = {"c4": _from_c4, "wikitext2": _from_wikitext2}
    order = [name] + [key for key in loaders if key != name]
    last_err: Exception | None = None
    ds = None
    for key in order:
        try:
            print(f"[wanda_prune] loading calibration dataset '{key}' ...", flush=True)
            ds = loaders[key]()
            break
        except Exception as exc:  # noqa: BLE001 - deliberate fallback chain
            print(f"[wanda_prune] '{key}' failed ({exc}); trying next option...", flush=True)
            last_err = exc
    if ds is None:
        raise RuntimeError(f"could not load any calibration dataset: {last_err}")

    def tokenize(example):
        return tokenizer(
            example["text"],
            padding=False,
            max_length=max_seq_length,
            truncation=True,
            add_special_tokens=False,
        )

    return ds.map(tokenize, remove_columns=ds.column_names)


def report_sparsity(model) -> float:
    import torch.nn as nn

    total = 0
    zeros = 0
    for module in model.modules():
        if isinstance(module, nn.Linear):
            weight = module.weight.data
            total += weight.numel()
            zeros += int((weight == 0).sum().item())
    return (zeros / total) if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="HF model id or local checkpoint path")
    parser.add_argument("--output", required=True, help="Output directory for the pruned checkpoint")
    parser.add_argument("--sparsity", type=float, required=True, help="Target unstructured sparsity fraction, e.g. 0.5 for 50%%")
    parser.add_argument("--calibration-dataset", default="c4", choices=["c4", "wikitext2"])
    parser.add_argument("--num-calibration-samples", type=int, default=128)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not (0.0 < args.sparsity < 1.0):
        sys.exit(f"--sparsity must be strictly between 0 and 1 (got {args.sparsity})")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from llmcompressor import oneshot
    from llmcompressor.modifiers.pruning.wanda import WandaPruningModifier

    print(f"[wanda_prune] loading {args.model} ...", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    dataset = build_calibration_dataset(
        tokenizer, args.calibration_dataset, args.num_calibration_samples,
        args.max_seq_length, args.seed,
    )

    recipe = WandaPruningModifier(
        sparsity=args.sparsity,
        mask_structure="0:0",  # unstructured only, per current scope
        targets="Linear",
        ignore=["lm_head"],
    )

    print(
        f"[wanda_prune] calibrating WandaPruningModifier "
        f"(sparsity={args.sparsity}, samples={len(dataset)}, "
        f"max_seq_length={args.max_seq_length}) ...",
        flush=True,
    )
    oneshot(
        model=model,
        dataset=dataset,
        recipe=recipe,
        max_seq_length=args.max_seq_length,
        num_calibration_samples=len(dataset),
    )

    achieved = report_sparsity(model)
    print(
        f"[wanda_prune] achieved overall Linear-layer sparsity: {achieved:.4f} "
        f"(target {args.sparsity})",
        flush=True,
    )

    print(f"[wanda_prune] saving pruned checkpoint to {args.output} ...", flush=True)
    model.save_pretrained(args.output, safe_serialization=True)
    tokenizer.save_pretrained(args.output)
    print("[wanda_prune] done.", flush=True)


if __name__ == "__main__":
    main()
