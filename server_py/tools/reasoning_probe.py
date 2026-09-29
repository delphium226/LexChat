"""P4.10 lever probe: what the pinned model does with a reasoning or output cap.

Two things, both cheap:

  --limits   the model's published limits from OpenRouter's models endpoint
             (no key needed): context, max completion tokens, whether
             reasoning is mandatory, the supported efforts, the prices, and
             the supported parameters.
  (default)  one tiny non-streaming call per configuration on a fixed arithmetic
             puzzle (no lawyer's text), printing the finish reason, completion
             and reasoning tokens, content length, the answer, seconds and cost.

What it established on google/gemini-3.1-pro-preview (Session 28): with no
`reasoning` field the model reasons in the `high` range, about twice `medium`,
not at the endpoint's advertised `medium` default; `reasoning.max_tokens` lands
token-for-token on an effort level (512 on `low`, 16000 on `high`) rather than
acting as a hard budget; a top-level `max_tokens` binds, and at 800 changed the
answer. One draw per configuration: a probe, not a measurement of quality.

    python -m tools.reasoning_probe --limits
    python -m tools.reasoning_probe [CONFIG ...]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROMPT = ("How many integers n with 1 <= n <= 3000 have the property that the sum of the "
          "decimal digits of n is a prime number AND n itself is a perfect square? "
          "Work it out carefully, then reply with only the final number.")

CONFIGS = {
    "default": {},
    "effort=low": {"reasoning": {"effort": "low"}},
    "effort=medium": {"reasoning": {"effort": "medium"}},
    "effort=high": {"reasoning": {"effort": "high"}},
    "reasoning.max_tokens=512": {"reasoning": {"max_tokens": 512}},
    "reasoning.max_tokens=6000": {"reasoning": {"max_tokens": 6000}},
    "reasoning.max_tokens=16000": {"reasoning": {"max_tokens": 16000}},
    "max_tokens=800": {"max_tokens": 800},
    "max_tokens=4000": {"max_tokens": 4000},
}

MODELS_URL = "https://openrouter.ai/api/v1/models"


def limits_line(m: dict) -> list:
    """The fields of one models-endpoint entry that bear on a cap."""
    top = m.get("top_provider") or {}
    return [
        f"{m.get('id')}",
        f"  context_length {m.get('context_length')}, "
        f"max_completion_tokens {top.get('max_completion_tokens')}",
        f"  reasoning {json.dumps(m.get('reasoning'))}",
        f"  pricing prompt {((m.get('pricing') or {}).get('prompt'))}, completion "
        f"{((m.get('pricing') or {}).get('completion'))}, internal_reasoning "
        f"{((m.get('pricing') or {}).get('internal_reasoning'))} (USD per token)",
        f"  supported_parameters {', '.join(m.get('supported_parameters') or [])}",
    ]


async def _limits(model_ids: list) -> int:
    import httpx

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(MODELS_URL)
        r.raise_for_status()
    found = {m["id"]: m for m in r.json().get("data") or [] if m.get("id") in model_ids}
    for mid in model_ids:
        if mid not in found:
            print(f"{mid}: not listed")
            continue
        print("\n".join(limits_line(found[mid])))
    return 0


def outcome_line(name: str, seconds: float, body: dict) -> tuple:
    """(printed line, cost) for one non-streaming response body."""
    u = body.get("usage") or {}
    ch = (body.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = (msg.get("content") or "").strip()
    err = ch.get("error") or body.get("error")
    cost = float(u.get("cost") or 0.0)
    line = (f"{name:<28} {seconds:6.1f}s finish={ch.get('finish_reason')}/"
            f"{ch.get('native_finish_reason')} completion={u.get('completion_tokens')} "
            f"reasoning={(u.get('completion_tokens_details') or {}).get('reasoning_tokens')} "
            f"content={len(content)}ch answer={content[:20]!r} cost=${cost:.4f}")
    if err:
        line += f" error={(err.get('message') if isinstance(err, dict) else str(err))[:80]!r}"
    return line, cost


async def _probe(names: list, model: Optional[str]) -> int:
    import httpx

    from tools.seam_replay import _provider_cfg

    cfg = await _provider_cfg({})
    base = (cfg.get("base_url") or "https://openrouter.ai/api/v1").rstrip("/")
    total = 0.0
    async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=30, read=600)) as c:
        for name in names:
            payload = {"model": model or cfg["model"], "temperature": 0, "stream": False,
                       "messages": [{"role": "user", "content": PROMPT}],
                       "usage": {"include": True}, **CONFIGS[name]}
            t0 = time.perf_counter()
            r = await c.post(f"{base}/chat/completions", json=payload,
                             headers={"Authorization": f"Bearer {cfg['api_key']}"})
            if r.status_code != 200:
                print(f"{name:<28} HTTP {r.status_code} {r.text[:200]}")
                continue
            line, cost = outcome_line(name, time.perf_counter() - t0, r.json())
            total += cost
            print(line)
    print(f"total ${total:.4f}")
    return 0


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="reasoning_probe")
    p.add_argument("configs", nargs="*", help=f"any of: {', '.join(CONFIGS)} "
                                              "(default: all)")
    p.add_argument("--limits", action="store_true",
                   help="print the models endpoint's limits instead; no key, no spend")
    p.add_argument("--model", default=None,
                   help="default: the model in app_settings (--limits: the pinned "
                        "model and the summarisation model)")
    args = p.parse_args(list(argv) if argv is not None else None)
    if args.limits:
        return asyncio.run(_limits([args.model] if args.model else [
            "google/gemini-3.1-pro-preview", "google/gemini-3-flash-preview"]))
    unknown = [c for c in args.configs if c not in CONFIGS]
    if unknown:
        raise SystemExit(f"unknown config(s): {', '.join(unknown)}")
    return asyncio.run(_probe(args.configs or list(CONFIGS), args.model))


if __name__ == "__main__":
    raise SystemExit(main())
