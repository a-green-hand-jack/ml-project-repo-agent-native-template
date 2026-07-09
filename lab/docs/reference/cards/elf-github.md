# ELF GitHub Source Card

Source: `https://github.com/lillian039/ELF`

Local clone: `code/external/ELF`

Remote clone: `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case/ELF`

Active branch inspected: `pytorch_elf`

Active commit inspected: `b29d8833609e9ab7f67cd9da39435ac5cea04837`

Earlier baseline commit on `main`:
`5098bf28b5e9b52c329970a7e4e1cc28251c76e6`

Observed files used for this case:

- `README.md`
- `requirements.txt`
- `scripts/launch.sh`
- `scripts/eval_ppl.py`
- `src/train.py`
- `src/eval.py`
- `src/generation.py`
- `src/train_step.py`
- `src/configs/config.py`
- `src/utils/train_utils.py`

Notes:

- The README reports that the main branch is a JAX implementation written and
  tested on TPUs.
- The `pytorch_elf` branch README reports a PyTorch port with converted
  Hugging Face checkpoints and PyTorch-oriented launch examples.
- The case did not verify model metrics, checkpoint loading, dataset loading,
  or training.
- The lightweight EPFL smoke was limited to clone/read checks, Python syntax
  compilation, YAML parse, shell syntax, and dependency availability checks.
