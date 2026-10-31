#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 body-rewrite 规则合并进已转换的 SR 模块，并补全 MITM。"""
import argparse
import json
import re

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


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--script-url", required=True)
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    with open(args.module, encoding="utf-8") as f:
        text = f.read()
    header, secs = split_sections(text)
    with open(args.rules, encoding="utf-8") as f:
        rules = [l for l in f.read().split("\n") if l.strip() and not l.startswith("#")]
    rules = [l.replace("__SCRIPT_URL__", args.script_url) for l in rules]

    secs = [(n, ls) for n, ls in secs]
    names = [n for n, _ in secs]
    # 幂等：先剔除上次运行留下的 body-rewrite-NNN 行，否则重跑一次变 192 条
    body_re = re.compile(r"^\s*body-rewrite-\d{3}\s*=")
    if "Script" in names:
        i = names.index("Script")
        kept = [l for l in secs[i][1] if not body_re.match(l)]
        secs[i] = ("Script", kept + rules)
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
        # 不要求 pattern 后紧跟 script-path：字段顺序变更时旧写法会静默变成 0 条
        m = re.search(r"\bpattern=([^,]+)", l)
        if m:
            pats.append(m.group(1))
    missing = []
    for p in pats:
        for h in hosts_of_pattern(p):
            if (h not in hosts and h not in missing
                    and not any(h.endswith(x.lstrip("*")) for x in hosts if x.startswith("*"))):
                missing.append(h)
    # 排序保证可重复构建（否则上游顺序微调会产生无意义 diff）；集合相同，功能等价
    hosts = sorted(set(hosts + missing), key=str.lower)
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
    with open(args.module, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)

    info = {"script_rules": len(rules), "mitm_added": missing,
            "mitm_total": len(hosts), "bytes": len(txt.encode())}
    print(json.dumps(info, ensure_ascii=False, indent=1))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
