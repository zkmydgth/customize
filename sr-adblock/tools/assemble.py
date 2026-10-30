#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 body-rewrite 规则合并进已转换的 SR 模块，并补全 MITM。"""
import argparse
import json
import os
import re
import sys

SEC_RE = re.compile(r"^\[([^\[\]]+)\]\s*$")


def split_sections(text):
    header, out, cur = [], [], None
    for line in text.split("\n"):
        m = SEC_RE.match(line)
        if m:
            cur = m.group(1).strip()
            out.append((cur, []))
            continue
        (header if cur is None else out[-1][1]).append(line)
    return header, out


def _expand(s, limit=128):
    """展开 (a|b)? 形式，返回具体域名列表"""
    s = s.replace("(?:", "(")
    res = [s]
    while True:
        changed = False
        nxt = []
        for cur in res:
            m = re.search(r"\(([^()]*)\)(\?)?", cur)
            if not m:
                nxt.append(cur)
                continue
            changed = True
            opts = m.group(1).split("|")
            if m.group(2):
                opts.append("")
            for o in opts:
                nxt.append(cur[:m.start()] + o + cur[m.end():])
        res = nxt
        if not changed or len(res) > limit:
            break
    return [x for x in res if not re.search(r"[()?|]", x)]


def hosts_of_pattern(pat):
    m = re.search(r"https\??:?\\?/\\?/((?:[A-Za-z0-9_.()|?:\\-]|\\.)+)", pat)
    if not m:
        return []
    raw = m.group(1).replace("\\", "")
    raw = raw.split("/")[0].strip(".")
    if not raw:
        return []
    out = []
    for h in _expand(raw):
        h = h.strip(".")
        if re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z0-9-]+", h) or re.fullmatch(r"\d+\.\d+\.\d+\.\d+", h):
            out.append(h)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--script-url", required=True)
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    text = open(args.module, encoding="utf-8").read()
    header, secs = split_sections(text)
    rules = [l for l in open(args.rules, encoding="utf-8").read().split("\n")
             if l.strip() and not l.startswith("#")]
    rules = [l.replace("__SCRIPT_URL__", args.script_url) for l in rules]

    secs = [(n, ls) for n, ls in secs]
    names = [n for n, _ in secs]
    if "Script" in names:
        i = names.index("Script")
        secs[i] = ("Script", secs[i][1] + rules)
    else:
        secs.append(("Script", rules))

    # ---- MITM 补全 ----
    mitm = dict(secs).get("MITM", [])
    hosts = []
    for l in mitm:
        if l.strip().lower().startswith("hostname"):
            hosts = [h.strip() for h in l.split("=", 1)[1].split(",") if h.strip()]
    pats = []
    for l in rules:
        m = re.search(r"pattern=(\S+?),\s*script-path=", l)
        if m:
            pats.append(m.group(1))
    missing = []
    for p in pats:
        for h in hosts_of_pattern(p):
            if h not in hosts and not any(h.endswith(x.lstrip("*")) for x in hosts if x.startswith("*")):
                if h not in missing:
                    missing.append(h)
    if missing:
        hosts = hosts + missing
        names = [n for n, _ in secs]
        i = names.index("MITM")
        secs[i] = ("MITM", ["hostname = " + ",".join(hosts)])

    out = list(header)
    for n, ls in secs:
        while ls and not ls[-1].strip():
            ls = ls[:-1]
        out.append("")
        out.append("[%s]" % n)
        out.extend(ls)
    txt = "\n".join(out).rstrip() + "\n"
    open(args.module, "w", encoding="utf-8", newline="\n").write(txt)

    info = {"script_rules": len(rules), "mitm_added": missing,
            "mitm_total": len(hosts), "bytes": len(txt.encode())}
    print(json.dumps(info, ensure_ascii=False, indent=1))
    if args.report:
        json.dump(info, open(args.report, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
