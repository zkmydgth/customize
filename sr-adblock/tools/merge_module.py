#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把另一个 SR 模块的规则合并进主模块（用于 deezertidal 去广告部分）。

合并策略（保守，主模块优先）：
  - Rule        追加到 `# __LOCAL_EXTRA_END__` 之后；无标记则追加段末
  - URL Rewrite 追加段末；pattern 已存在则跳过
  - Script      追加段末；pattern 已存在则跳过（避免同 URL 双脚本互相覆盖）
  - Map Local   追加段末；整行去重
  - MITM        合并 hostname 并去重排序

用法:
  python3 tools/merge_module.py --main dist/blockAds.sr.module \
      --add /tmp/dz_ad.srmodule --report build/merge_dz.json
"""
import argparse
import json
import os
import re

SEC_RE = re.compile(r"^\[([^\]]+)\]\s*$")


def split_module(path):
    header, secs, order = [], {}, []
    cur = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            t = line.rstrip("\n")
            m = SEC_RE.match(t.strip())
            if m:
                cur = m.group(1).strip()
                if cur not in secs:
                    secs[cur] = []
                    order.append(cur)
                continue
            if cur is None:
                header.append(t)
            else:
                # 保留注释与空行（`# __LOCAL_EXTRA_END__` 靠它定位）
                secs[cur].append(t)
    return header, secs, order


def pattern_of(line):
    m = re.search(r"\bpattern=([^,]+)", line)
    if m:
        return m.group(1).strip()
    m = re.match(r"^(.+?)\s+\S+$", line)
    return m.group(1).strip() if m else None


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--add", required=True)
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    def real(lines):
        return [l for l in lines if l.strip() and not l.strip().startswith("#")]

    mh, ms, _ = split_module(a.main)
    _, als, _ = split_module(a.add)

    stats = {}
    # ---- Rule ----
    have = set(real(ms.get("Rule", [])))
    new_rules = [l for l in real(als.get("Rule", [])) if l not in have]
    if new_rules:
        rules = ms.setdefault("Rule", [])
        try:
            pos = rules.index("# __LOCAL_EXTRA_END__") + 1
        except ValueError:
            pos = len(rules)
        ms["Rule"] = rules[:pos] + new_rules + rules[pos:]
    stats["rule"] = len(new_rules)

    # ---- URL Rewrite（pattern 去重） ----
    have = {pattern_of(l) for l in real(ms.get("URL Rewrite", []))}
    add_u = []
    for l in real(als.get("URL Rewrite", [])):
        p = pattern_of(l)
        if p and p not in have:
            have.add(p)
            add_u.append(l)
    ms.setdefault("URL Rewrite", []).extend(add_u)
    stats["url_rewrite"] = len(add_u)

    # ---- Script（pattern 去重，主模块优先） ----
    have = {pattern_of(l) for l in real(ms.get("Script", []))}
    add_s, skipped_s = [], 0
    for l in real(als.get("Script", [])):
        p = pattern_of(l) or l
        if p in have:
            skipped_s += 1
            continue
        have.add(p)
        add_s.append(l)
    ms.setdefault("Script", []).extend(add_s)
    stats["script"] = len(add_s)
    stats["script_skipped_same_pattern"] = skipped_s

    # ---- Map Local ----
    have = set(real(ms.get("Map Local", [])))
    add_m = [l for l in real(als.get("Map Local", [])) if l not in have]
    ms.setdefault("Map Local", []).extend(add_m)
    stats["map_local"] = len(add_m)

    # ---- MITM ----
    def hosts(lines):
        out = []
        for l in lines:
            if l.strip().lower().startswith("hostname") and "=" in l:
                out += [h.strip() for h in l.split("=", 1)[1].split(",") if h.strip()]
        return out

    h_main, h_add = hosts(ms.get("MITM", [])), hosts(als.get("MITM", []))
    merged = sorted({h.lower() for h in h_main + h_add}, key=str.lower)
    stats["mitm_added"] = len(merged) - len({h.lower() for h in h_main})
    stats["mitm_total"] = len(merged)
    if merged:
        ms["MITM"] = ["hostname = " + ",".join(merged)]

    # ---- 输出（段顺序：原有顺序优先） ----
    def counts():
        return {s: len(real(v)) for s, v in ms.items()}

    c = counts()
    out = []
    for l in mh:
        if l.startswith("#  合并统计:"):
            continue
        out.append(l)
    # 重写统计行
    for i, l in enumerate(out):
        if l.startswith("#  保留统计:"):
            out[i] = ("#  保留统计: Rule %d / URL Rewrite %d / Map Local %d / Script %d / MITM %d hosts"
                      % (c.get("Rule", 0), c.get("URL Rewrite", 0), c.get("Map Local", 0),
                         c.get("Script", 0), len(merged)))
            break

    order = ["Rule", "Host", "URL Rewrite", "Map Local", "Script", "MITM"]
    for s in order:
        if s not in ms or not ms[s]:
            continue
        out.append("")
        out.append("[%s]" % s)
        out.extend(ms[s])
    for s in ms:
        if s in order:
            continue
        out.append("")
        out.append("[%s]" % s)
        out.extend(ms[s])

    with open(a.main, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).rstrip() + "\n")

    stats["bytes"] = os.path.getsize(a.main)
    stats["counts"] = c
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
