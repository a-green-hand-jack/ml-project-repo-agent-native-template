# Code Status

## Current Focus

ELF `pytorch_elf` template case smoke on EPFL CVLAB RunAI environment without
launching GPU/TPU training.

## Active Runs

- `pytorch_elf` branch smoke on local and EPFL remote clones:
  Python syntax, YAML config parse, and `scripts/launch.sh` shell syntax.
- EPFL persistent-env runtime smoke:
  `.venv-pytorch` under the remote case root imports PyTorch ELF dependencies,
  imports ELF train/eval/generation modules, loads the existing ELF-B config,
  and runs a tiny synthetic CPU forward pass.

## Blockers

- No blocker remains for CPU dependency/import smoke.
- GPU training, checkpoint inference, dataset loading, and metric reproduction
  have not been run and should not be claimed from the current evidence.

## Remote Mapping

- Server: `epfl-haas`
- Remote case root:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case`
- Remote ELF clone:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case/ELF`
- Branch: `pytorch_elf`
- Commit: `b29d8833609e9ab7f67cd9da39435ac5cea04837`
- Runtime env:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case/.venv-pytorch`
