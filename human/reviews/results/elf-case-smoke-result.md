# ELF Case Smoke Result

Date: 2026-07-08

Outcome: baseline smoke completed.

- Local case workspace:
  `/Users/jieke/Projects/research-template-cases/elf-case`
- EPFL remote path:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case`
- Source commit:
  `5098bf28b5e9b52c329970a7e4e1cc28251c76e6`
- Remote smoke:
  clone/read checks plus `python3 -m py_compile` on selected ELF source files.
- Validation:
  `PYTHONPATH=/Users/jieke/Projects/research-project-harness/src python3 -m research_project_harness validate .`

Limits:

- No dependency installation.
- No GPU/TPU training.
- No checkpoint inference.
- No reproduced metrics claimed.

## PyTorch Branch Follow-up

Date: 2026-07-08

Outcome: `pytorch_elf` lightweight smoke completed; runtime dependency smoke
blocked.

- Active branch:
  `pytorch_elf`
- Active commit:
  `b29d8833609e9ab7f67cd9da39435ac5cea04837`
- Local and EPFL remote checks:
  Python source syntax smoke over 9 files, YAML parse over 7 config files, and
  `bash -n scripts/launch.sh`.
- EPFL dependency availability check:
  `torch`, `transformers`, and `datasets` are not installed in the current
  login Python environment; `yaml` is available.

Limits:

- No dependency installation.
- No GPU training.
- No checkpoint inference.
- No reproduced metrics claimed.

## Persistent Env Runtime Follow-up

Date: 2026-07-08

Outcome: EPFL persistent-env runtime smoke completed.

- Runtime env:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case/.venv-pytorch`
- EPFL private-skill pattern used:
  persistent `uv`, persistent `UV_CACHE_DIR`, persistent
  `UV_PYTHON_INSTALL_DIR`, and a project-scoped env rather than login Python.
- Dependency imports:
  `torch 2.12.1+cu130`, `transformers 4.44.2`, `datasets 5.0.0`,
  `yaml 6.0.3`, `einops 0.8.2`, `huggingface_hub 0.36.2`,
  `sacrebleu 2.6.0`, `rouge_score`, `wandb 0.28.0`, and `muon`.
- ELF runtime smoke:
  imported config/model/train/eval/generation modules, loaded
  `train_owt_ELF-B.yml`, applied safe overrides, and ran a tiny synthetic CPU
  ELF forward pass with output shape `(2, 4, 8)` and logits shape `(2, 4, 32)`.

Limits:

- No GPU was available in this login-node smoke (`torch.cuda.is_available()`
  was false).
- No dataset loading, checkpoint inference, training loop, generation loop, or
  metric reproduction was attempted.
