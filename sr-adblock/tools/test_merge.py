#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并器回归：去重口径 + 风险闸门。"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

MODULE = """#!name=t

[Rule]
DOMAIN-SUFFIX,existing.com,REJECT
DOMAIN,exact.example,REJECT
"""

SOURCE = """# QX style
host-suffix, existing.com, reject
host-suffix, sub.existing.com, reject
host, exact.example, reject
host-suffix, newad.example, reject
host-suffix, temu.com, reject
host-keyword, trackerword, reject
host-suffix, allowed.example, direct
host-suffix, l.qq.com, reject
host-keyword, trace.qq.com, reject
host-suffix, xy.com, reject
"""


def main():  # noqa: C901
    fails = []
    with tempfile.TemporaryDirectory() as td:
        m = os.path.join(td, "m.module")
        s = os.path.join(td, "s.list")
        r = os.path.join(td, "r.json")
        with open(m, "w", encoding="utf-8") as f:
            f.write(MODULE)
        with open(s, "w", encoding="utf-8") as f:
            f.write(SOURCE)

        p = subprocess.run([sys.executable, "tools/merge_extra.py", "--module", m,
                            "--source", s, "--min-len", "7", "--report", r],
                           capture_output=True, text=True)
        if p.returncode != 0:
            fails.append("merge 崩溃: " + (p.stderr or "")[-200:])
        else:
            with open(r, encoding="utf-8") as f:
                info = json.load(f)
            with open(m, encoding="utf-8") as f:
                txt = f.read()
            if "newad.example" not in txt:
                fails.append("新规则未并入")
            if txt.count("existing.com") != 1:
                fails.append("重复规则未去重（existing.com 出现 %d 次）" % txt.count("existing.com"))
            if "sub.existing.com" in txt:
                fails.append("被父级后缀覆盖的子域未去重")
            if "temu.com" in txt:
                fails.append("知名主站未被风险闸门拦截")
            if "trackerword" not in txt:
                fails.append("DOMAIN-KEYWORD 未并入")
            if "l.qq.com" in txt or "trace.qq.com" in txt:
                fails.append("范围过宽的域名未被闸门拦截")
            if "xy.com" in txt:
                fails.append("短域名未被 --min-len 过滤（误伤风险）")
            if "allowed.example" in txt:
                fails.append("非 reject 规则被误并入")
            if info.get("added") != 2:
                fails.append("add 计数异常: %r" % info.get("added"))

    if fails:
        print("MERGE FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("MERGE PASS: 去重（含父级后缀覆盖）/ 风险主站拦截 / 非 reject 忽略")
    return 0


if __name__ == "__main__":
    sys.exit(main())
