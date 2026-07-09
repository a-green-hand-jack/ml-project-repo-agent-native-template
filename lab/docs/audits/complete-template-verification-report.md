# Complete Template Verification Report

Case: ELF on `pytorch_elf`

Baseline:

- Case repo: `/Users/jieke/Projects/research-template-cases/elf-case`
- Remote root:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case`
- Source branch: `pytorch_elf`
- Source commit: `b29d8833609e9ab7f67cd9da39435ac5cea04837`
- Runtime env:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case/.venv-pytorch`

Commands:

```bash
remote-bash --upload epfl-haas \
  /mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case -
# Created/reused .venv-pytorch with persistent uv cache and installed
# ELF requirements from the pytorch_elf checkout.

remote-bash --upload epfl-haas \
  /mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case -
# Imported runtime dependencies and ran the tiny ELF CPU-forward smoke.

PYTHONPATH=/Users/jieke/Projects/research-project-harness/src \
  python3 -m research_project_harness validate .

cd code
python3 -m compileall -q src eval experiments scripts tests
uv run --no-project --with pytest --python 3.11 python -m pytest -q tests
```

Findings:

- EPFL login Python was correctly treated as insufficient for runtime testing.
  The test used the private-skill PVC pattern instead: persistent `uv`,
  persistent `UV_CACHE_DIR`, persistent `UV_PYTHON_INSTALL_DIR`, and a
  project-scoped `.venv-pytorch`.
- Dependency imports passed for `torch 2.12.1+cu130`, `transformers 4.44.2`,
  `datasets 5.0.0`, `yaml 6.0.3`, `einops 0.8.2`,
  `huggingface_hub 0.36.2`, `sacrebleu 2.6.0`, `rouge_score`,
  `wandb 0.28.0`, and `muon`. `muon-optimizer` appears in `uv pip list` as
  version `0.1.0`; its import module is `muon`.
- ELF runtime smoke passed: config/model/train/eval/generation imports,
  `train_owt_ELF-B.yml` loading, safe override application, and one synthetic
  CPU forward through a tiny `ELF` instance. The forward returned shape
  `(2, 4, 8)` and decoder logits shape `(2, 4, 32)`.
- Template validator passed on the real case: `OK: project harness valid`.
- Code scaffold checks passed: compileall exited 0 and pytest reported
  `2 passed`.
- Disposable-copy negative probes all failed closed as expected:
  template-mode mutation, missing active `paper/main.tex`, inactive required
  `code` component, missing evidence link, missing evidence provenance, and
  unsafe `activate-component.py code` overwrite.

Replay result:

- The complete `research-project-template` case now exercises the expected
  active surfaces: `reference/`, `code/`, `paper/`, project memory boards,
  human review result, docs audit, project-local skill, component validator,
  disposable-copy stress probes, EPFL remote mapping, persistent remote env,
  and non-training ELF runtime smoke.

Remaining debt:

- No GPU job was submitted, and `torch.cuda.is_available()` was false in the
  login-node smoke.
- No dataset loading, checkpoint loading, training loop, generation loop,
  metric reproduction, or paper-quality claim is supported by this evidence.
