# ELF README Summary

This summary is source-reported from `code/external/ELF/README.md` and should
not be treated as independently reproduced model evidence.

- ELF is presented as an implementation for the paper "ELF: Embedded Language
  Flows".
- The initial baseline used the main branch README, which describes JAX plus
  TPU setup, with separate PyTorch branches for PyTorch ELF and progressive
  distillation.
- The active follow-up uses the `pytorch_elf` branch, whose README describes a
  PyTorch implementation, converted Hugging Face checkpoints, PyTorch
  requirements, training commands, and evaluation commands.
- The repository provides training and evaluation entrypoints under `src/`.
- `pytorch_elf` requirements include `torch`, `transformers`, `datasets`,
  `huggingface-hub`, `sacrebleu`, `rouge-score`, `wandb`, and
  `muon-optimizer`.
- `pytorch_elf` README evaluation examples use converted Hugging Face
  checkpoints and datasets.

Case implication:

- A non-destructive template harness smoke can check source layout and Python
  syntax without expensive GPU/TPU work.
- Any stronger claim about running ELF or reproducing numbers needs an explicit
  persistent PyTorch environment, checkpoint/data access, and dependency plan.
