"""badcase 自动回归：批量生成并校验失败模式是否被诊断。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_pipeline.generate_cli import generate
from ai_pipeline.types import GenerateRequest


def load_badcases(root: Path) -> list[dict]:
    path = root / "ai_pipeline" / "cases" / "badcase" / "cases.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_one_case(root: Path, provider: str, case: dict) -> dict:
    data = case.get("input", {})
    req = GenerateRequest(
        prompt=f"badcase回归: {case.get('intent', '')}",
        audio_profile=data.get("audio_profile", "balanced"),
        geometry_targets=data.get("geometry_targets", ["circle"]),
        style_profile=data.get("style_profile", "minimal"),
        constraints={"target_glsl": "330", "badcase_id": case.get("id", "unknown")},
        seed=17,
    )

    try:
        result = generate(req, root, provider=provider)
        diag = "\n".join(result.diagnostics)
        expected_hits = [sig for sig in case.get("expected_signals", []) if sig in diag]
        quality_ok = result.quality_report.get("returncode", 1) == 0
        passed = quality_ok and len(expected_hits) > 0
        return {
            "id": case.get("id"),
            "passed": passed,
            "quality_ok": quality_ok,
            "expected_hits": expected_hits,
            "diagnostics": result.diagnostics,
        }
    except Exception as e:
        return {
            "id": case.get("id"),
            "passed": False,
            "quality_ok": False,
            "expected_hits": [],
            "diagnostics": [f"exception: {e}"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 badcase 自动回归")
    parser.add_argument("--provider", default="openai", choices=["openai", "mock"])
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    cases = load_badcases(root)

    reports: list[dict] = []
    for case in cases:
        rep = run_one_case(root, args.provider, case)
        reports.append(rep)
        print(json.dumps(rep, ensure_ascii=False))
        if args.fail_fast and not rep["passed"]:
            break

    total = len(reports)
    passed = sum(1 for r in reports if r["passed"])
    summary = {"total": total, "passed": passed, "failed": total - passed}
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

