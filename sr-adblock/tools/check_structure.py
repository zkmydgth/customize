#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块结构断言（第④层：边界/结构）。

用法: python3 tools/check_structure.py [--module dist/blockAds.sr.module]
退出码 1 = 结构不合格。
"""
import argparse
import re
import sys

SEC_RE = re.compile(r"^\[([^\[\]]+)\]\s*$")


def load(path):
    secs, cur = {}, None
    with open(path, encoding="utf-8") as f:
        raw = f.read().split("\n")
    for line in raw:
        line = line.rstrip("\n")
        m = SEC_RE.match(line)
        if m:
            cur = m.group(1)
            secs.setdefault(cur, [])
            continue
        if cur and line.strip() and not line.lstrip().startswith("#"):
            secs[cur].append(line)
    return secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", default="dist/blockAds.sr.module")
    a = ap.parse_args()
    secs = load(a.module)
    fails = []

    def need(cond, msg):
        if not cond:
            fails.append(msg)

    need("Rule" in secs, "缺少 [Rule]")
    need("Script" in secs, "缺少 [Script]")
    need("MITM" in secs, "缺少 [MITM]")
    need("URL Rewrite" in secs, "缺少 [URL Rewrite]")
    need("Map Local" in secs, "缺少 [Map Local]")
    need("Body Rewrite" not in secs, "含 SR 不支持的 [Body Rewrite]")
    need("Header Rewrite" not in secs, "含 SR 不支持的 [Header Rewrite]")

    need(len(secs.get("Rule", [])) > 2000, "Rule 条数异常: %d" % len(secs.get("Rule", [])))
    need(len(secs.get("Script", [])) > 300, "Script 条数异常: %d" % len(secs.get("Script", [])))

    body_rules = [l for l in secs.get("Script", []) if l.startswith("body-rewrite-")]
    need(len(body_rules) == 96, "Body Rewrite 脚本数 %d != 96" % len(body_rules))
    need(all("script-path=" in l for l in body_rules), "有脚本行缺 script-path")
    need(all("requires-body=1" in l for l in body_rules), "有脚本行缺 requires-body=1")

    mitm = " ".join(secs.get("MITM", []))
    need("hostname" in mitm, "MITM 缺 hostname")
    need("%append%" not in mitm.lower(), "MITM 仍含 Surge 专有 %APPEND%")
    need("%insert%" not in mitm.lower(), "MITM 仍含 Surge 专有 %INSERT%")
    hosts = []
    for l in secs.get("MITM", []):
        if l.lower().startswith("hostname"):
            hosts = [h.strip() for h in l.split("=", 1)[1].split(",") if h.strip()]
    need(len(hosts) > 800, "MITM hostname 过少: %d" % len(hosts))
    need(len(set(hosts)) == len(hosts), "MITM hostname 有重复")
    need(not any(" " in h for h in hosts), "MITM hostname 含空格（解析失败）")

    # Rule 段不得出现 Map Local / URL Rewrite 语法（放错段 = 规则不生效）
    misplaced = [l for l in secs.get("Rule", [])
                 if "data-type=" in l or " status-code=" in l or l.endswith(" - reject")]
    need(not misplaced, "Rule 段含其他段语法（放错段）: %d 条，例: %s"
         % (len(misplaced), misplaced[0][:60] if misplaced else ""))

    # Map Local 段不得出现纯 Rule 语法（只有 TYPE,value,policy 三段且无 data-type）
    bad_ml = [l for l in secs.get("Map Local", [])
              if "data-type=" not in l and l.count(",") == 2]
    need(not bad_ml, "Map Local 段疑似混入 Rule 语法: %d 条" % len(bad_ml))

    urw = secs.get("URL Rewrite", [])
    need(sum(1 for l in urw if l.endswith("reject-tinygif")) >= 100,
         "reject-tinygif 条数不足（Map Local 转换丢失）")

    if fails:
        print("STRUCTURE FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("STRUCTURE PASS: Rule=%d Script=%d BodyRewrite=%d MITM=%d URLRewrite=%d"
          % (len(secs["Rule"]), len(secs["Script"]), len(body_rules), len(hosts), len(urw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
