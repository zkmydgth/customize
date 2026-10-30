#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从上游 Surge 模块中抽出 [Body Rewrite] 段 -> JSON（供 gen_scripts.py 使用）"""
import json
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "upstream.module"
DST = sys.argv[2] if len(sys.argv) > 2 else "/tmp/bodyrewrite.json"

with open(SRC, encoding="utf-8", errors="replace") as f:
    lines = f.read().replace("\r\n", "\n").split("\n")
inb, rows = False, []
for l in lines:
    if l.strip() == "[Body Rewrite]":
        inb = True
        continue
    if inb and re.match(r"^\[[^\]]+\]\s*$", l):
        inb = False
    if inb and l.strip() and not l.lstrip().startswith("#"):
        rows.append(l)

out = []
for r in rows:
    m = re.match(r"^http-response-jq\s+(\S+)\s+'(.*)'\s*$", r, re.S)
    if m:
        out.append({"type": "jq", "pattern": m.group(1), "expr": m.group(2).strip()})
    elif r.startswith("http-response "):
        out.append({"type": "replace", "raw": r})
    else:
        out.append({"type": "unknown", "raw": r})

with open(DST, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps({"total": len(out),
                  "jq": sum(1 for x in out if x["type"] == "jq"),
                  "replace": sum(1 for x in out if x["type"] == "replace"),
                  "unknown": sum(1 for x in out if x["type"] == "unknown")}, ensure_ascii=False))
