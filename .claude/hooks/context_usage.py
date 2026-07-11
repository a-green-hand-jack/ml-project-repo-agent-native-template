#!/usr/bin/env python3
"""Context usage helper —— 从 transcript 算「精确」上下文占用。

单一真源：块 1（statusline 仪表盘）与块 2（阈值提醒 hook）共用本模块，避免两处
各写一套估算逻辑而漂移。

精确来源（已由探测确认，见 plans/20260711-context-orchestration.zh.md）：
transcript JSONL 最后一条 assistant message 的 `message.usage`：
    context_tokens = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
这是当前上下文的精确 token 数，不是字符/4 近似。

窗口大小：显式 --window > 环境 CLAUDE_CTX_WINDOW > 按 model_id 推断 > 默认 200000。
Opus [1m] 类 1M 窗口的 session，statusline 会带 model_id 让本模块推出 1e6；
不带 model 信息的 hook 路径可用 CLAUDE_CTX_WINDOW 覆盖。

无第三方依赖。可 import，也可 CLI：
    python3 context_usage.py --tokens     <transcript>            -> 打印 token 数或空
    python3 context_usage.py --percent    <transcript> [--window N|--model ID] -> 打印整数百分比或空
    python3 context_usage.py --statusline <transcript> [--window N|--model ID] -> 打印 "🧠 NN%"（阈值着色）
所有失败路径都静默降级（打印空 + exit 0），绝不阻断调用方。
"""
import argparse
import json
import os
import sys

DEFAULT_WINDOW = 200_000
YELLOW_AT = 65  # ≥ 黄
RED_AT = 80     # ≥ 红


def window_for_model(model_id: str | None) -> int:
    """按 model id 粗判窗口。识别 1M 上下文（如 opus-4-8[1m]）。"""
    if not model_id:
        return DEFAULT_WINDOW
    mid = model_id.lower()
    if "[1m]" in mid or "-1m" in mid or "_1m" in mid or "1m]" in mid:
        return 1_000_000
    return DEFAULT_WINDOW


def resolve_window(window: int | None = None, model_id: str | None = None) -> int:
    """显式 window > env CLAUDE_CTX_WINDOW > model 推断 > 默认。"""
    if window and window > 0:
        return window
    env = os.environ.get("CLAUDE_CTX_WINDOW", "").strip()
    if env:
        try:
            v = int(env)
            if v > 0:
                return v
        except ValueError:
            pass
    return window_for_model(model_id)


def _int(v: object) -> int:
    return v if isinstance(v, int) and v >= 0 else 0


def _scan_transcript(transcript_path: str | None) -> tuple[int | None, str | None]:
    """单次遍历 transcript，返回 (上下文精确 token, 最后 model id)。

    单遍是刻意的：percent() 的默认路径（无 window/model/env）既要 token 又要 model 推窗口，
    合并成一次读避免大 transcript（接近满时可达数十 MB、每轮 UserPromptSubmit 触发）被读两遍。

    token = 最后一条带 usage 的 message 的 input+cache_read+cache_creation。
    model = 最后一条带 model 的 message 的 id（transcript 存 base id，不带 `[1m]`——
    故 1M 窗口从此认不出，仍靠 CLAUDE_CTX_WINDOW；statusline 走 `.model.id` 才含 `[1m]`）。
    找不到 / 读不了 → (None, None)。对非 dict 行（半写入/畸形产出的合法标量）显式跳过，
    确保「所有失败路径静默降级、绝不抛异常冒泡」的契约不被 obj.get 破坏。
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return (None, None)
    last_usage = None
    last_model = None
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(obj, dict):
                    continue  # 合法但非对象的行（如 `42`、`"x"`）不能 .get，跳过
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if isinstance(usage, dict) and any(
                    k in usage
                    for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
                ):
                    last_usage = usage  # 取最后一条 —— 最贴近当前上下文
                model = msg.get("model")
                if isinstance(model, str):
                    last_model = model
    except OSError:
        return (None, None)
    if last_usage is None:
        return (None, last_model)
    tokens = (
        _int(last_usage.get("input_tokens"))
        + _int(last_usage.get("cache_read_input_tokens"))
        + _int(last_usage.get("cache_creation_input_tokens"))
    )
    return (tokens, last_model)


def context_tokens(transcript_path: str | None) -> int | None:
    """读 transcript 求上下文精确 token（找不到/无 usage → None）。"""
    return _scan_transcript(transcript_path)[0]


def model_from_transcript(transcript_path: str | None) -> str | None:
    """从 transcript 取最后 model id，作为窗口推断的兜底（见 _scan_transcript）。"""
    return _scan_transcript(transcript_path)[1]


def percent(transcript_path: str | None, window: int | None = None, model_id: str | None = None) -> int | None:
    tokens, transcript_model = _scan_transcript(transcript_path)  # 单遍拿齐 token + model
    if tokens is None:
        return None
    # 无显式 window / model / env 时，兜底用 transcript 认出的 model 推窗口。
    if window is None and model_id is None and not os.environ.get("CLAUDE_CTX_WINDOW", "").strip():
        model_id = transcript_model
    win = resolve_window(window, model_id)
    if win <= 0:
        return None
    return min(999, round(100 * tokens / win))


def _colorize(text: str, pct: int) -> str:
    """按阈值着色；NO_COLOR 环境变量置位时不加 ANSI（statusline 期望输出 ANSI，故不判 tty）。"""
    if os.environ.get("NO_COLOR"):
        return text
    if pct >= RED_AT:
        return f"\033[31m{text}\033[0m"   # 红
    if pct >= YELLOW_AT:
        return f"\033[33m{text}\033[0m"   # 黄
    return text


def statusline_segment(transcript_path: str | None, window: int | None = None, model_id: str | None = None) -> str:
    pct = percent(transcript_path, window, model_id)
    if pct is None:
        return ""  # 无数据 → 不展示这段（降级，不报错）
    return _colorize(f"🧠 {pct}%", pct)


def _cli() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("transcript", nargs="?", default=None)
    ap.add_argument("--tokens", action="store_true")
    ap.add_argument("--percent", action="store_true")
    ap.add_argument("--statusline", action="store_true")
    ap.add_argument("--window", type=int, default=None)
    ap.add_argument("--model", type=str, default=None)
    args = ap.parse_args()
    try:
        if args.tokens:
            t = context_tokens(args.transcript)
            print("" if t is None else t)
        elif args.statusline:
            print(statusline_segment(args.transcript, args.window, args.model))
        else:  # 默认 --percent
            p = percent(args.transcript, args.window, args.model)
            print("" if p is None else p)
    except Exception:  # 兜底：绝不让调用方因本模块崩溃
        print("")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
