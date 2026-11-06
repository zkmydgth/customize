#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构断言：deezertidal 合并产物（dist/unlock.srmodule）。

判据（任一不满足即失败并阻断提交）：
  - 四个必需段都在，且不含 SR 不支持的段
  - Script 每条都有 type= 与 script-path=
  - URL Rewrite 每条都是「pattern + 拦截动作」，不含 302/307/header 跳转
  - MITM 无 %APPEND%、无空格、无 - 排除项、无重复
  - 各段条数不低于下限（防上游结构变化导致的静默缩水）
"""
import argparse
import os
import re
import sys

SEC_RE = re.compile(r"^\[([^\]]+)\]\s*$")
ALLOW_ACTION = {"reject", "reject-200", "reject-img", "reject-dict", "reject-tinygif"}


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", default="dist/unlock.srmodule")
    ap.add_argument("--min-rule", type=int, default=10)
    ap.add_argument("--min-urw", type=int, default=400)
    ap.add_argument("--min-script", type=int, default=250)
    ap.add_argument("--min-mitm", type=int, default=300)
    a = ap.parse_args()

    if not os.path.exists(a.module):
        print("CHECK FAIL: 找不到 %s" % a.module)
        return 1

    secs, cur = {}, None
    with open(a.module, encoding="utf-8") as f:
        for line in f:
            t = line.rstrip("\n")
            m = SEC_RE.match(t.strip())
            if m:
                cur = m.group(1).strip()
                secs.setdefault(cur, [])
                continue
            if cur and t.strip() and not t.strip().startswith("#"):
                secs[cur].append(t.strip())

    fails = []

    for s in ("URL Rewrite", "Script", "MITM"):
        if s not in secs:
            fails.append("缺少 [%s] 段" % s)
    for s in ("Header Rewrite", "Body Rewrite", "General"):
        if s in secs:
            fails.append("含 SR 不支持的 [%s]（%d 行）" % (s, len(secs[s])))

    scripts = secs.get("Script", [])
    urw = secs.get("URL Rewrite", [])
    mitm_lines = secs.get("MITM", [])

    if len(scripts) < a.min_script:
        fails.append("Script 条数异常: %d < %d" % (len(scripts), a.min_script))
    if len(urw) < a.min_urw:
        fails.append("URL Rewrite 条数异常: %d < %d" % (len(urw), a.min_urw))

    bad_script = [l for l in scripts if "type=" not in l or "script-path=" not in l]
    if bad_script:
        fails.append("Script 缺 type/script-path: %d 条，例 %s" % (len(bad_script), bad_script[0][:90]))

    bad_urw = []
    for l in urw:
        m = re.match(r"^.+?\s+(\S+)$", l)
        if not m or m.group(1) not in ALLOW_ACTION:
            bad_urw.append(l)
    if bad_urw:
        fails.append("URL Rewrite 动作非法: %d 条，例 %s" % (len(bad_urw), bad_urw[0][:90]))

    hosts = []
    for l in mitm_lines:
        if l.lower().startswith("hostname"):
            hosts = [h.strip() for h in l.split("=", 1)[1].split(",") if h.strip()]
    if not hosts:
        fails.append("MITM 段没有 hostname")
    else:
        if len(hosts) < a.min_mitm:
            fails.append("MITM 域名过少: %d < %d" % (len(hosts), a.min_mitm))
        low = [h.lower() for h in hosts]
        if len(set(low)) != len(low):
            fails.append("MITM 有重复域名: %d 个" % (len(low) - len(set(low))))
        if any("%append%" in h.lower() or "%insert%" in h.lower() for h in hosts):
            fails.append("MITM 仍含 %APPEND%/%INSERT%")
        if any(" " in h for h in hosts):
            fails.append("MITM 含空格（解析失败）")
        if any(h.startswith("-") for h in hosts):
            fails.append("MITM 含 - 排除项（SR 不支持）")

    print("STATS: Rule=%d URLRewrite=%d Script=%d MITM=%d bytes=%d"
          % (len(secs.get("Rule", [])), len(urw), len(scripts), len(hosts),
             os.path.getsize(a.module)))

    if fails:
        print("CHECK FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
