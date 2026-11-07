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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repair import hosts_of_pattern  # noqa: E402
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
    """Script 取 pattern= 的值；URL Rewrite 取首个 token。

    旧实现对 URL Rewrite 用 `^(.+?)\\s+\\S+$`，会把 `pattern replacement 302`
    里的 replacement 也吞进 key，导致"同 pattern 换动作"被误判重复而静默丢弃。
    """
    m = re.search(r"\bpattern=([^,]+)", line)
    if m:
        return m.group(1).strip()
    m = re.match(r"^(\S+)\s", line)
    return m.group(1) if m else None


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

    # ---- Script ----
    # 去重键用「名称 + pattern」而不是单纯的 pattern：
    # 解锁模块里有大量「多个 App 共用同一个 pattern」的情况
    # （例如 RevenueCat 的 8 个订阅校验脚本共用 v1/(receipts|subscribers)/*），
    # 只按 pattern 去重会把其中 7 个 App 的解锁脚本整批丢掉。
    def script_key(line):
        name = line.split("=", 1)[0].strip()
        return (name, pattern_of(line) or line)

    have = {script_key(l) for l in real(ms.get("Script", []))}
    add_s, skipped_s = [], 0
    for l in real(als.get("Script", [])):
        k = script_key(l)
        if k in have:
            skipped_s += 1
            continue
        have.add(k)
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
                out += [re.sub(r"^%(APPEND|INSERT)%\s*", "", h.strip(), flags=re.I)
                    for h in l.split("=", 1)[1].split(",")
                    if h.strip() and re.sub(r"^%(APPEND|INSERT)%\s*", "", h.strip(), flags=re.I)]
        return out

    def _clean(h):
        """与 convert.build_mitm 同一套清洗：SR 不认的写法一律剔除。"""
        h = re.sub(r"^%(APPEND|INSERT)%\s*", "", h.strip(), flags=re.I).lower()
        if not h or "append" in h or "insert" in h:
            return None
        if h.startswith("-"):                       # Surge 的排除项，语义相反
            return None
        if "?" in h or ".." in h:                   # 非合法通配 / 空标签
            return None
        if re.search(r":0$", h):                    # 端口 0
            return None
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", h):  # 纯 IP
            return None
        if re.fullmatch(r"\d+\.\d+\.\d+\.\*", h):   # IP 通配
            return None
        return h

    h_main = [x for x in (_clean(h) for h in hosts(ms.get("MITM", []))) if x]
    h_add = [x for x in (_clean(h) for h in hosts(als.get("MITM", []))) if x]
    merged = sorted(set(h_main) | set(h_add), key=str.lower)
    stats["mitm_added"] = len(merged) - len({h.lower() for h in h_main})
    stats["mitm_total"] = len(merged)
    # 合并进来的规则引用到的域名也必须进 MITM（dz 的模块自身 MITM 常不全）
    _ref = set()
    for _l in real(ms.get("URL Rewrite", [])) + real(ms.get("Script", [])) + real(ms.get("Map Local", [])):
        _m = re.search(r"\bpattern=([^,]+)", _l) or re.match(r"^(\S+)\s", _l)
        if not _m:
            continue
        for _h in hosts_of_pattern(_m.group(1)):
            _h = _h.lower()
            if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", _h) or len(_h) < 6:
                continue
            _ref.add(_h)
    _add = sorted({x for x in (_clean(h) for h in (_ref - {h.lower() for h in merged})) if x})
    if _add:
        merged = sorted(set(merged) | set(_add), key=str.lower)
        stats["mitm_coverage_added"] = len(_add)
    if merged:
        ms["MITM"] = ["hostname = %APPEND% " + ",".join(merged)]

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
    def trim_tail(body):
        while body and not body[-1].strip():
            body = body[:-1]
        return body

    for s in order:
        if s not in ms or not real(ms[s]):
            continue
        body = trim_tail(ms[s])
        while out and not out[-1].strip():
            out.pop()
        out.append("")
        out.append("[%s]" % s)
        out.extend(body)
    for s in ms:
        if s in order or not real(ms[s]):
            continue
        body = trim_tail(ms[s])
        while out and not out[-1].strip():
            out.pop()
        out.append("")
        out.append("[%s]" % s)
        out.extend(body)

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
