#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变异测试：验证测试套件真的能抓到缺陷（0 逃逸 / 0 跳过）

按 NAS 记忆《MP插件开发运维手册》§3.2 规约：
  - 片段失配 = skipped = 失败（不允许静默跳过）
  - finally 无条件还原，结束核对 sha256
  - 一步一跑，每步 timeout
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = os.environ.get("UPSTREAM", "/tmp/upstream.module")
os.chdir(ROOT)

MUTATIONS = [
    {
        "name": "M1 同一URL只应用第一条规则（重复pattern失守）",
        "file": "tools/gen_scripts.py",
        "old": "  if (!matched.length) { $done({}); return; }",
        "new": "  if (!matched.length) { $done({}); return; }\n  matched = matched.slice(0, 1);",
        "regen": True,
        "test": ["node", "tools/test_script.js"],
        "timeout": 120,
    },
    {
        "name": "M2 不识别 (?i) 内联标志",
        "file": "tools/gen_scripts.py",
        "old": '  while (p.indexOf("(?i)") === 0) { flags += "i"; p = p.slice(4); }',
        "new": '  /* mutated: no inline flag handling */',
        "regen": True,
        "test": ["node", "tools/test_script.js"],
        "timeout": 120,
    },
    {
        "name": "M3 map 对非数组不报错（吞掉类型错误）",
        "file": "tools/jq_runtime.js",
        "old": "          else throw new Error('map');",
        "new": "          else { /* mutated */ }",
        "regen": True,
        "test": ["python3", "tools/test_equiv.py", "--inputs", "3"],
        "timeout": 400,
    },
    {
        "name": "M4 has 对 null 不返回 false",
        "file": "tools/jq_runtime.js",
        "old": "          if (v === null || v === undefined) return [false];",
        "new": "          /* mutated: null 不再返回 false */",
        "regen": True,
        "test": ["python3", "tools/test_equiv.py", "--inputs", "3"],
        "timeout": 400,
    },
    {
        "name": "M5 MITM 不清理 %APPEND%（结构缺陷）",
        "file": "tools/repair.py",
        "old": '    h = re.sub(r"^%(APPEND|INSERT)%\\s*", "", h, flags=re.I).strip().lower()',
        "new": "    h = h.strip().lower()  # mutated",
        "regen": False,
        "build": True,
        "test": ["python3", "tools/check_structure.py", "--module", "dist/_mut.module"],
        "timeout": 120,
    },
]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build():
    subprocess.run(["python3", "tools/gen_scripts.py"], capture_output=True, timeout=120)
    subprocess.run(["python3", "tools/convert.py", UPSTREAM, "dist/_mut.module",
                    "--report", "/tmp/_mut_report.json"], capture_output=True, timeout=120)
    subprocess.run(["python3", "tools/assemble.py", "--module", "dist/_mut.module",
                    "--rules", "build/body-rewrite.rules",
                    "--script-url", "https://example.invalid/x.js",
                    "--report", "/tmp/_mut_assemble.json"], capture_output=True, timeout=120)


def main():
    results = []
    for m in MUTATIONS:
        path = m["file"]
        with open(path, encoding="utf-8") as f:
            src = f.read()
        h0 = sha(path)
        if m["old"] not in src:
            results.append({"name": m["name"], "status": "SKIPPED",
                            "note": "变异片段未命中（防护未生效！）"})
            continue
        if src.count(m["old"]) != 1:
            results.append({"name": m["name"], "status": "SKIPPED",
                            "note": "片段出现 %d 次，不唯一" % src.count(m["old"])})
            continue
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(src.replace(m["old"], m["new"], 1))
            if m.get("regen") or m.get("build"):
                build()
            p = subprocess.run(m["test"], capture_output=True, text=True, timeout=m["timeout"])
            caught = p.returncode != 0
            results.append({
                "name": m["name"],
                "status": "CAUGHT" if caught else "ESCAPED",
                "exit": p.returncode,
                "tail": (p.stdout or p.stderr).strip().split("\n")[-1][:120],
            })
        finally:
            with open(path, "w", encoding="utf-8") as f:
                f.write(src)
            if m.get("regen") or m.get("build"):
                build()
            assert sha(path) == h0, "还原失败: " + path

    caught = sum(1 for r in results if r["status"] == "CAUGHT")
    escaped = sum(1 for r in results if r["status"] == "ESCAPED")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print("\n变异汇总: %d 捕获 / %d 逃逸 / %d 跳过" % (caught, escaped, skipped))
    if escaped or skipped:
        print("⚠️ 防护未生效（逃逸或跳过均视为失败）")
        return 1
    print("✅ 0 逃逸 0 跳过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
