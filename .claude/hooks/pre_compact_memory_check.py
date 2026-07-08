#!/usr/bin/env python3
"""PreCompact advisory hook。

compact 前提醒：`memory/current-status.md` 是否最近更新过。
这是提醒，不是硬阻止——compact 在 context 满时本就脆弱，硬 block 反而危险。
因此本 hook 永远 exit 0，只把提醒写到 stderr（会显示给 Claude）。

无第三方依赖。
"""
import os
import sys
import time

STATUS_FILE = "memory/current-status.md"
STALE_SECONDS = 30 * 60  # 30 分钟内更新过算「新鲜」


def main() -> None:
    # 尽量在 repo 根运行；hook 的 cwd 通常是项目根。
    if not os.path.exists(STATUS_FILE):
        print(
            f"[pre_compact] 提醒：未找到 {STATUS_FILE}。compact 前建议先落盘状态"
            "（用 checkpoint-writer 写 objective/decisions/changed files/next steps）。",
            file=sys.stderr,
        )
        sys.exit(0)

    age = time.time() - os.path.getmtime(STATUS_FILE)
    if age > STALE_SECONDS:
        mins = int(age // 60)
        print(
            f"[pre_compact] 提醒：{STATUS_FILE} 已 {mins} 分钟未更新。"
            "compact 会丢历史——先确认当前状态、决策、改动文件、下一步已写入。"
            "参考 .agent/checklists/pre-compact.md。",
            file=sys.stderr,
        )
    else:
        print(f"[pre_compact] {STATUS_FILE} 新鲜（{int(age//60)} 分钟内更新）。", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
