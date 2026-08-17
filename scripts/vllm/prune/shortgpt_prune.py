#!/usr/bin/env python3
"""ShortGPT-style structured layer pruning (no fine-tuning).

Computes a Block Influence (BI) score per transformer decoder layer from
calibration data - BI_i = 1 - mean cosine similarity between a layer's input
and output hidden states, so a low BI means the layer barely changes its
input and is a good removal candidate - then physically deletes the
lowest-BI layers and re-saves a smaller checkpoint (fewer decoder layers,
config.num_hidden_layers updated to match). No retraining/fine-tuning.

Works on any Hugging Face causal LM whose decoder stack is
`model.model.layers` (an nn.ModuleList) - true for the Llama/Qwen2/Granite-
family architectures these scripts target.

Reference: "ShortGPT: Layers in Large Language Models are More Redundant
Than You Expect", https://arxiv.org/abs/2403.03853
"""
from __future__ import annotations

import argparse
import sys


def build_calibration_texts(name: str, num_samples: int, seed: int) -> list[str]:
    from datasets import load_dataset

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
        return texts

    def _from_wikitext2():
        raw = load_dataset("wikitext", "wikitext-2-raw-v1", split="train")
        raw = raw.shuffle(seed=seed)
        texts = [t for t in raw["text"] if len(t.strip()) > 100][:num_samples]
        if len(texts) < num_samples:
            raise RuntimeError(f"only found {len(texts)}/{num_samples} usable WikiText-2 samples")
        return texts

    loaders = {"c4": _from_c4, "wikitext2": _from_wikitext2}
    order = [name] + [key for key in loaders if key != name]
    last_err: Exception | None = None
    for key in order:
        try:
            print(f"[shortgpt_prune] loading calibration dataset '{key}' ...", flush=True)
            return loaders[key]()
        except Exception as exc:  # noqa: BLE001 - deliberate fallback chain
            print(f"[shortgpt_prune] '{key}' failed ({exc}); trying next option...", flush=True)
            last_err = exc
    raise RuntimeError(f"could not load any calibration dataset: {last_err}")


def compute_block_influence(model, tokenizer, texts, max_seq_length, device):
    import torch
    import torch.nn.functional as F

    num_layers = model.config.num_hidden_layers
    sim_sum = torch.zeros(num_layers, dtype=torch.float64)
    sim_count = torch.zeros(num_layers, dtype=torch.float64)

    model.eval()
    with torch.no_grad():
        for i, text in enumerate(texts):
            enc = tokenizer(
                text, return_tensors="pt", truncation=True, max_length=max_seq_length,
            ).to(device)
            if enc["input_ids"].shape[1] < 2:
                continue
            out = model(**enc, output_hidden_states=True, use_cache=False)
            # hidden_states: tuple of (num_layers + 1) tensors [batch, seq, hidden].
            # hidden_states[0]     = embedding output = input to layer 0
            # hidden_states[k]     = output of layer k-1 = input to layer k
            # hidden_states[k + 1] = output of layer k
            hidden_states = out.hidden_states
            for layer_idx in range(num_layers):
                h_in = hidden_states[layer_idx][0].float()
                h_out = hidden_states[layer_idx + 1][0].float()
                cos = F.cosine_similarity(h_in, h_out, dim=-1)  # [seq_len]
                sim_sum[layer_idx] += cos.sum().item()
                sim_count[layer_idx] += cos.numel()
            if (i + 1) % 10 == 0:
                print(f"[shortgpt_prune] calibrated {i + 1}/{len(texts)} samples", flush=True)

    mean_sim = sim_sum / sim_count.clamp(min=1)
    block_influence = 1.0 - mean_sim
    return block_influence.tolist()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="HF model id or local checkpoint path")
    parser.add_argument("--output", required=True, help="Output directory for the pruned checkpoint")
    parser.add_argument("--sparsity", type=float, required=True, help="Fraction of decoder layers to remove, e.g. 0.25 for 25%%")
    parser.add_argument("--calibration-dataset", default="c4", choices=["c4", "wikitext2"])
    parser.add_argument("--num-calibration-samples", type=int, default=128)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not (0.0 < args.sparsity < 1.0):
        sys.exit(f"--sparsity must be strictly between 0 and 1 (got {args.sparsity})")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[shortgpt_prune] loading {args.model} ...", flush=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, trust_remote_code=True,
    ).to(device)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if not hasattr(model, "model") or not hasattr(model.model, "layers"):
        sys.exit(
            f"'{args.model}' does not expose model.model.layers (an nn.ModuleList of "
            "decoder blocks) - this script only supports Llama/Qwen2/Granite-family "
            "architectures."
        )

    texts = build_calibration_texts(args.calibration_dataset, args.num_calibration_samples, args.seed)

    print("[shortgpt_prune] computing per-layer Block Influence scores ...", flush=True)
    bi_scores = compute_block_influence(model, tokenizer, texts, args.max_seq_length, device)

    num_layers = model.config.num_hidden_layers
    num_to_remove = round(num_layers * args.sparsity)
    num_to_remove = max(1, min(num_layers - 1, num_to_remove))  # never remove every layer

    ranked = sorted(range(num_layers), key=lambda i: bi_scores[i])  # ascending BI = most redundant first
    remove_idx = set(ranked[:num_to_remove])
    keep_idx = [i for i in range(num_layers) if i not in remove_idx]

    print("[shortgpt_prune] per-layer BI scores (lower = more redundant):", flush=True)
    for i, score in enumerate(bi_scores):
        marker = " <-- REMOVED" if i in remove_idx else ""
        print(f"  layer {i:3d}: BI={score:.4f}{marker}", flush=True)
    print(
        f"[shortgpt_prune] removing {num_to_remove}/{num_layers} layers "
        f"({num_to_remove / num_layers:.1%}): {sorted(remove_idx)}",
        flush=True,
    )

    import torch.nn as nn

    model.model.layers = nn.ModuleList([model.model.layers[i] for i in keep_idx])
    model.config.num_hidden_layers = len(keep_idx)

    print(f"[shortgpt_prune] saving pruned checkpoint to {args.output} ...", flush=True)
    model.save_pretrained(args.output, safe_serialization=True)
    tokenizer.save_pretrained(args.output)
    print("[shortgpt_prune] done.", flush=True)


if __name__ == "__main__":
    main()
