# 迁移自 ELF-template-case：provenance / source-visibility board

## Provenance

- **PRV-ELF-GITHUB-REPO** — public-github-repository
  - source: https://github.com/lillian039/ELF
  - branch: `pytorch_elf`, commit: `b29d8833609e9ab7f67cd9da39435ac5cea04837`
  - baseline_main_commit: `5098bf28b5e9b52c329970a7e4e1cc28251c76e6`
  - visibility: public
  - notes: 旧周期作为 `research-template-case-harness-test` 的真实案例源导入；先在 main 建 baseline，
    再切到 `pytorch_elf` 做 EPFL 友好的后续 smoke。本仓库未 vendor 该 clone（见
    `lab/docs/audits/` 的功能测试报告中关于 `lab/code/external/` 的记录）。

## Source visibility

- **VIS-ELF-PUBLIC-GITHUB** — https://github.com/lillian039/ELF，visibility: public。
  可在公开案例报告中正常引用；不得把凭据、私密 EPFL 运维细节或重型生成产物带入
  paper-facing 内容。
- **VIS-EPFL-REMOTE-PATH** — EPFL 远端执行路径，visibility: internal。
  仅用于本地工作区的案例操作与报告；不得作为 paper-facing 产物发布，也不得含凭据。
