#!/usr/bin/env python3
"""Simple injector: replace {{USER_INPUT}} in a template with value from getinput module.

Behavior:
 - Import the given module and prefer calling get_user_input(); else read USER_INPUT.
 - If import fails, run the module as a script and capture stdout.
 - Replace `{{USER_INPUT}}` in the template; if placeholder missing, prepend `USER_INPUT: ...`.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def _get_from_module(path: Path) -> str:
    """Load module and return USER_INPUT attribute; if unavailable run script stdout."""
    spec = importlib.util.spec_from_file_location("gin", str(path))
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            return _run_and_capture(path)
        if hasattr(mod, "USER_INPUT"):
            return str(getattr(mod, "USER_INPUT"))
    return _run_and_capture(path)


def _run_and_capture(path: Path) -> str:
    try:
        out = subprocess.check_output([sys.executable, str(path)], text=True, stderr=subprocess.STDOUT)
        return out.strip()
    except subprocess.CalledProcessError:
        return ""


def _escape(text: str) -> str:
    return text.replace('```', "` ` `")


def build(template: str, user_input: str) -> str:
    safe = _escape(user_input)
    if "{{USER_INPUT}}" in template:
        return template.replace("{{USER_INPUT}}", safe)
    return f"USER_INPUT: {safe}\n\n" + template


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--getinput", default="getinput.py", help="Path to getinput module (default: getinput.py)")
    p.add_argument("--template", default="prompts/shader_prompt_audio_nebula.txt")
    p.add_argument("--out", default="prompts/filled_shader_prompt.txt")
    args = p.parse_args()

    gp = Path(args.getinput)
    tp = Path(args.template)
    op = Path(args.out)

    if not gp.exists():
        print(f"getinput not found: {gp}")
        sys.exit(2)
    if not tp.exists():
        print(f"template not found: {tp}")
        sys.exit(2)

    ui = _get_from_module(gp)
    if not ui:
        print("Warning: USER_INPUT empty or could not be obtained")

    txt = tp.read_text(encoding="utf-8")
    filled = build(txt, ui)

    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(filled, encoding="utf-8")
    print(f"Wrote: {op}")


if __name__ == "__main__":
    main()
