#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 tools/extra_rules.txt 里的每一条都真的进了产物。

动机：2026-10-30 推送补充规则后，CI 因推送可见性延迟 checkout 到旧文件，
产物少了 7 条却仍然 success —— 这类"规则没生效但流程全绿"必须被自动挡住。

用法: python3 tools/check_extra.py [--module dist/blockAds.sr.module]
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC_RE = re.compile(r"^\[([^\[\]]+)\]\s*$")


def load_extra():
    path = os.path.join(ROOT, "tools", "extra_rules.txt")
    out, cur = {}, None
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = SEC_RE.match(line)
            if m:
                cur = m.group(1)
                out.setdefault(cur, [])
                continue
            if cur:
                out[cur].append(line)
    return out


def sections(path):
    d, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = SEC_RE.match(line)
            if m:
                cur = m.group(1)
                d.setdefault(cur, set())
                continue
            if cur and line and not line.startswith("#"):
                d[cur].add(line)
    return d


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", default=os.path.join(ROOT, "dist/blockAds.sr.module"))
    a = ap.parse_args()

    extra = load_extra()
    if not extra:
        # 文件缺失/为空时不能 PASS —— 那等于"没有补充规则要核对"，
        # 而真实情况往往是文件丢了，产物里的补充规则整批消失
        print("EXTRA FAIL: tools/extra_rules.txt 缺失或为空")
        return 1

    secs = sections(a.module)
    # MITM 段在产物里是单行 hostname=a,b,c，需单独解析
    mitm_hosts = set()
    with open(a.module, encoding="utf-8") as f:
        for line in f:
            t = line.strip()
            if t.lower().startswith("hostname") and "=" in t:
                mitm_hosts = {h.strip().lower() for h in t.split("=", 1)[1].split(",") if h.strip()}

    missing = []
    for sec, rules in extra.items():
        if sec == "MITM":
            for h in rules:
                if h.lower() not in mitm_hosts:
                    missing.append((sec, h))
            continue
        target = secs.get(sec, set())
        for r in rules:
            if r not in target:
                missing.append((sec, r))

    if missing:
        print("EXTRA FAIL: %d 条补充规则未出现在产物中" % len(missing))
        for sec, r in missing[:20]:
            print("  [%s] %s" % (sec, r[:110]))
        return 1

    total = sum(len(v) for v in extra.values())
    print("EXTRA PASS: %d 条补充规则全部生效（%s）"
          % (total, ", ".join("%s=%d" % (k, len(v)) for k, v in extra.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
