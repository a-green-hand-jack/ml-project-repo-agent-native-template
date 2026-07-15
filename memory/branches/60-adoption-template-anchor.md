# Branch Status: 60-adoption-template-anchor

## Purpose
Implement issue #60 adoption template-anchor support under the approved D1-D4 contract.

## Branch / base
- Local worktree branch: `p2a-60-adoption-template-anchor`
- Published topic ref: `fix/60-adoption-template-anchor`
- Worktree: `/home/user/.paseo/worktrees/1kaz3672/60-adoption-template-anchor`
- Base: `origin/main` = `e3d89a812058d56647df34171cc9c8f9b0c32d7a` (clean at start)

## Invariant
Bootstrap's public behavior remains unchanged; adoption never writes an anchor outside a successful, unblocked, non-dry-run normalize, and never writes through a symlink or an origin conflict.

## Variation axis
Adoption gains an explicit required `--origin` contract and create/confirm of `.template.toml` through a narrow shared helper.

## Non-goals
Do not change `template-manifest.toml`, `scripts/template-sync.py`, template-sync smoke, root `CONTRACT.md`, remote configuration, protected bytes, runtime hooks, or issues #54-#59/#62/#63.

## Expected paths
- `scripts/adopt-existing-repo.py`
- `scripts/_template_anchor.py`
- `scripts/bootstrap-project.py`
- `lab/evals/adoption/run-adoption-smoke.py`
- `lab/evals/bootstrap/run-bootstrap-smoke.py`
- directly related adoption/bootstrap documentation and `scripts/ANATOMY.md`
- `memory/branches/60-adoption-template-anchor.md`

## Exit condition
Targeted smoke tests and governance checks pass; the worktree is committed and pushed to the topic branch. First adoption-to-template-sync integration remains pending issue #62 and a fresh verifier after #62 merges.
