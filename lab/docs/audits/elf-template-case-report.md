# Template Case Harness Report

Case:

- Source: `https://github.com/lillian039/ELF`
- Local case workspace: `/Users/jieke/Projects/research-template-cases/elf-case`
- Local source clone: `code/external/ELF`
- EPFL remote path:
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case`
- ELF baseline commit inspected:
  `5098bf28b5e9b52c329970a7e4e1cc28251c76e6`
- Active follow-up branch: `pytorch_elf`
- Active follow-up commit:
  `b29d8833609e9ab7f67cd9da39435ac5cea04837`

Baseline:

- Generated from the current upstream complete template on branch
  `research-project-template`.
- Case state populated in `reference/`, `memory/boards/`, `code/infra/`, and
  `code/docs/ops/`.
- No model metrics, training, checkpoint inference, or dataset loading were
  claimed as reproduced.
- Follow-up switched the local and EPFL remote ELF clones to `pytorch_elf` and
  repeated lightweight source/config/shell checks.

Commands:

```bash
PYTHONPATH=/Users/jieke/Projects/research-project-harness/src \
  python3 -m research_project_harness init \
  /Users/jieke/Projects/research-template-cases/elf-case

git clone --depth 1 https://github.com/lillian039/ELF code/external/ELF
git -C code/external/ELF rev-parse HEAD

epfl-runai whoami
remote-cmd epfl-haas /mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk -- pwd

remote-bash --upload epfl-haas \
  /mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk -
# Created llm/ELF-template-case idempotently and cloned/fetched ELF there.

remote-bash --upload epfl-haas \
  /mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case -
# Ran: python3 -m py_compile over selected ELF source entrypoints.

python3 -m py_compile \
  code/external/ELF/src/train.py \
  code/external/ELF/src/eval.py \
  code/external/ELF/src/generation.py \
  code/external/ELF/src/train_step.py \
  code/external/ELF/src/configs/config.py \
  code/external/ELF/src/utils/train_utils.py

python3 - <<'PY'
from pathlib import Path
files = [
    'code/external/ELF/src/train.py',
    'code/external/ELF/src/eval.py',
    'code/external/ELF/src/generation.py',
    'code/external/ELF/src/train_step.py',
    'code/external/ELF/src/configs/config.py',
    'code/external/ELF/src/utils/train_utils.py',
]
for f in files:
    compile(Path(f).read_text(encoding='utf-8'), f, 'exec')
print('syntax_ok', len(files))
PY

PYTHONPATH=/Users/jieke/Projects/research-project-harness/src \
  python3 -m research_project_harness validate .
```

PyTorch branch follow-up commands:

```bash
git -C code/external/ELF fetch origin '+refs/heads/*:refs/remotes/origin/*'
git -C code/external/ELF switch -C pytorch_elf origin/pytorch_elf
git -C code/external/ELF rev-parse HEAD

remote-bash --upload epfl-haas \
  /mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case -
# Fetched branches and switched remote clone to origin/pytorch_elf.

python3 - <<'PY'
from pathlib import Path
files = [
    'src/train.py', 'src/eval.py', 'src/generation.py', 'src/train_step.py',
    'src/configs/config.py', 'src/utils/train_utils.py',
    'src/utils/muon_utils.py', 'src/modules/model.py', 'scripts/eval_ppl.py',
]
root = Path('code/external/ELF')
for rel in files:
    compile((root / rel).read_text(encoding='utf-8'), str(root / rel), 'exec')
print('syntax_ok', len(files))
PY

python3 - <<'PY'
from pathlib import Path
import yaml
root = Path('code/external/ELF')
files = list((root / 'src/configs/training_configs').glob('*.yml')) + \
    list((root / 'src/configs/sampling_configs').glob('*.yml'))
for f in files:
    yaml.safe_load(f.read_text(encoding='utf-8'))
print('yaml_parse_ok', len(files))
PY

bash -n code/external/ELF/scripts/launch.sh

remote-bash --upload epfl-haas \
  /mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case -
# Ran equivalent Python syntax, YAML parse, shell syntax, and dependency
# availability checks on EPFL.
```

Results:

- Local ELF clone reached commit
  `5098bf28b5e9b52c329970a7e4e1cc28251c76e6`.
- `epfl-runai whoami` succeeded for the EPFL RunAI session.
- `remote-cmd` confirmed the PVC-backed working root exists.
- Remote idempotent setup created or reused
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case`,
  cloned ELF, read `README.md` and `requirements.txt`, and reported expected
  source files.
- Remote `python3 -m py_compile` passed for `train.py`, `eval.py`,
  `generation.py`, `train_step.py`, `configs/config.py`, and
  `utils/train_utils.py`.
- A no-write local syntax check printed `syntax_ok 6`; remote cleanup plus the
  same no-write syntax check printed `syntax_ok 6` and `pycache_left=false`.
- `rph validate .` passed after case ledger updates.
- Local and remote ELF clones are now on `pytorch_elf` commit
  `b29d8833609e9ab7f67cd9da39435ac5cea04837`.
- Local and remote `pytorch_elf` Python syntax smoke printed `syntax_ok 9`.
- Local and remote YAML config parse printed `yaml_parse_ok 7`.
- Local and remote `bash -n scripts/launch.sh` passed.
- EPFL login Python lacks `torch`, `transformers`, and `datasets`; runtime
  import smoke requires a persistent PyTorch environment.
- Follow-up persistent-env runtime smoke used
  `/mnt/cvlab/scratch/cvlab/home/hantzhan/code_jk/llm/ELF-template-case/.venv-pytorch`
  and passed dependency imports, ELF module imports, config loading, and one
  tiny synthetic CPU ELF forward pass.
- Disposable-copy template validator probes passed: template-mode mutation,
  missing active paper file, inactive required code component, missing evidence
  link, missing evidence provenance, and unsafe component reactivation were all
  rejected as expected.
- Code scaffold checks passed: `python3 -m compileall -q src eval experiments
  scripts tests` and `uv run --no-project --with pytest --python 3.11 python
  -m pytest -q tests` from `code/`.

Findings:

- Documentation friction: the template provides good canonical surfaces, but a
  real external source case needs a documented convention for whether a nested
  upstream clone belongs under `code/external/`, `reference/sources/`, or a
  worktree/submodule-like surface. This case used `code/external/ELF` and
  recorded provenance in `reference/`.
- Case ledger debt: checkpoint loading, dataset loading, GPU execution, and
  metric reproduction were not attempted. The persistent-env runtime smoke only
  supports dependency import and tiny synthetic CPU-forward claims.
- No upstream validator gap was proven by this baseline. The existing validator
  accepted the populated case and enforced linked claim/evidence/action/risk
  consistency.

Upstream candidates:

- Consider adding a short template note for third-party case-source placement:
  source clone, source card, provenance board, and whether nested Git
  repositories should be ignored, vendored, or linked externally.
- Consider a validator or documentation hint for experiment objects, since the
  current baseline can record remote smoke details but experiment field shape is
  mostly conventional rather than enforced.

Replay result:

- Baseline replay completed locally and remotely on 2026-07-08.

Remaining debt:

- Decide whether a short RunAI GPU job is needed after dependency import smoke.
- Do not promote any model-performance claim until checkpoint/data execution is
  actually run and recorded.
