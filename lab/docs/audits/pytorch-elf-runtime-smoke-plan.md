# PyTorch ELF Runtime Smoke Plan

Scope: `/Users/jieke/Projects/research-template-cases/elf-case/code/external/ELF`
branch `pytorch_elf`.

## EPFL Execution Result

Date: 2026-07-08

The recommended smoke was executed on EPFL from the remote checkout using the
PVC-backed env
`/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case/.venv-pytorch`.

Result:

- dependency imports passed for PyTorch, Transformers, Datasets, YAML, Einops,
  Hugging Face Hub, SacreBLEU, Rouge Score, WandB, and Muon
- ELF config/model/train/eval/generation imports passed
- `train_owt_ELF-B.yml` loaded and safe overrides applied
- tiny synthetic CPU forward passed with output shape `(2, 4, 8)` and decoder
  logits shape `(2, 4, 32)`

The smoke did not use GPU, dataset loading, checkpoint loading, training,
generation loops, or metric evaluation.

## Recommended Smoke

Run from the ELF checkout after installing `requirements.txt`:

```bash
cd /Users/jieke/Projects/research-template-cases/elf-case/code/external/ELF
PYTHONPATH="$PWD/src" python3 - <<'PY'
import torch, transformers, datasets

from configs.config import load_config_from_yaml, apply_config_overrides
from modules.model import ELF, ELF_models
import train, eval, generation

cfg = load_config_from_yaml("src/configs/training_configs/train_owt_ELF-B.yml")
cfg = apply_config_overrides(
    cfg,
    [
        "use_bf16=false",
        "use_compile=false",
        "online_eval=false",
        "num_samples=1",
    ],
)

model = ELF(
    text_encoder_dim=8,
    max_length=4,
    hidden_size=16,
    depth=1,
    num_heads=4,
    bottleneck_dim=4,
    num_time_tokens=1,
    num_self_cond_cfg_tokens=1,
    num_model_mode_tokens=1,
    vocab_size=32,
).eval()

with torch.no_grad():
    y, logits = model(
        torch.randn(2, 4, 8),
        torch.rand(2),
        attention_mask=torch.ones(2, 4),
        self_cond_cfg_scale=torch.ones(2),
        decoder_step_active=True,
    )

assert y.shape == (2, 4, 8), y.shape
assert logits.shape == (2, 4, 32), logits.shape
print(
    "OK",
    "torch", torch.__version__,
    "transformers", transformers.__version__,
    "datasets", datasets.__version__,
    "config_model", cfg.model,
    "registered_models", sorted(ELF_models),
)
PY
```

## Contract

- Exercises Python imports for `torch`, `transformers`, and `datasets`.
- Exercises ELF module imports for config loading, train/eval/generation entry modules, and model registry.
- Loads an existing YAML config and applies CLI-style config overrides.
- Constructs a tiny in-memory `ELF` instance directly, not `ELF-B`, to avoid large allocation.
- Runs one CPU-compatible forward pass with synthetic tensors.
- Does not call `AutoTokenizer.from_pretrained`, dataset loaders, checkpoint loaders, `scripts/launch.sh`, `train.py main`, or `eval.py main`.

## Expected Dependencies

Install the upstream runtime dependencies first:

```bash
python3 -m pip install -r requirements.txt
```

The local control-plane shell observed during the read-only planning pass had
`python3` but not `torch`, so this smoke failed there before import with:

```text
ModuleNotFoundError: No module named 'torch'
```

## GPU

No GPU is required. The proposed smoke stays on CPU and avoids bf16 autocast,
`torch.compile`, checkpoint loading, generation loops, online PPL, and WandB.

## Likely Failure Points

- Missing dependency: especially `torch`, `transformers`, `datasets`, `yaml`, `einops`, or the `muon` module provided by `muon-optimizer`.
- `PYTHONPATH` not pointing at `$PWD/src`, causing `configs`, `modules`, or `utils` imports to fail.
- Running from a different working directory: the sampled config references `src/configs/sampling_configs/uncond_sampling_configs.yml` as a relative path.
- Upstream API drift in PyTorch attention/autocast behavior.
- Installing incompatible dependency versions outside the constraints in `requirements.txt`.
