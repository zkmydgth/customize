#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 deezertidal/shadowrocket-rules 的 270 个单 App 模块合并成一个 SR 模块。

用法:
  python3 tools/dz_convert.py <仓库modules目录> <输出.srmodule> [--raw-url URL]

规则:
  - 段名大小写/尾空格归一（仓库里有 [mitm] [Mitm] "[MITM] " 等变体）
  - 丢弃 SR 不支持的段（Header Rewrite / Body Rewrite）
  - [MITM] 去掉 %APPEND%/%INSERT%，忽略 - 开头的排除项
  - [Script] 删掉 script-update-interval（SR 不认），按整行去重
  - [Rule] / [URL Rewrite] 去重，保持首次出现顺序
"""
import argparse
import json
import os
import re

SEC_RE = re.compile(r"^\[([^\]]+)\]\s*$")
UNLOCK_RE = re.compile(r"解锁|破解|会员|vip|premium|专业版|订阅|内购|高级版|unlock|crack", re.I)
AD_RE = re.compile(r"去广告|广告|净化|屏蔽|开屏|block|\bad\b|adblock", re.I)


def classify(path):
    """按 #!name / #!desc 判断模块类型：unlock / ad / other"""
    name = desc = ""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            t = line.strip()
            if t.startswith("#!name="):
                name = t[7:]
            elif t.startswith("#!desc="):
                desc = t[7:]
            elif t.startswith("#") or not t:
                continue
            elif t.startswith("["):
                break
    text = name + " " + desc
    u = bool(UNLOCK_RE.search(text))
    a = bool(AD_RE.search(text))
    if u:
        return "unlock", name, desc      # 含解锁即归解锁（both 也算）
    if a:
        return "ad", name, desc
    return "other", name, desc
DROP_SEC = {"header rewrite", "body rewrite", "general"}
KEEP = {"rule", "url rewrite", "map local", "script", "mitm"}
SEC_NAME = {"rule": "Rule", "url rewrite": "URL Rewrite", "map local": "Map Local",
            "script": "Script", "mitm": "MITM"}


def clean_script(line):
    line = re.sub(r",?\s*script-update-interval=[^,]*", "", line)
    line = re.sub(r",?\s*argument=[^,]*", "", line)
    line = re.sub(r"requires-body=(true|1)\b", "requires-body=1", line, flags=re.I)
    line = re.sub(r",\s*,", ",", line)
    return line.rstrip(" ,")


ALLOW_ACTION = ("reject", "reject-200", "reject-img", "reject-dict", "reject-tinygif")


LEGACY_RE = re.compile(r"^(http-(?:request|response))\s+(\S+)\s+(.+)$")


def clean_legacy_script(line, idx, stats):
    """旧版 Surge 位置参数语法 -> key=value

    `http-response <pattern> requires-body=1,max-size=0,script-path=...`
      -> `legacy-NN = type=http-response, pattern=<pattern>, requires-body=1, ...`
    """
    m = LEGACY_RE.match(line.strip())
    if not m:
        return None
    typ, pat, rest = m.group(1), m.group(2), m.group(3)
    if "script-path=" not in rest:
        return None
    fields = [x.strip() for x in rest.split(",") if x.strip()]
    if not any(f.startswith("type=") for f in fields):
        fields.insert(0, "type=" + typ)
    if not any(f.startswith("pattern=") for f in fields):
        fields.insert(1, "pattern=" + pat)
    stats["legacy_script_converted"] += 1
    return "legacy-%02d = %s" % (idx, ", ".join(fields))


def clean_url_rewrite(line, stats):
    """规范化 URL Rewrite；只保留拦截类，丢弃跳转类。

    - `pattern - reject`  -> `pattern reject`（去掉 Surge 的空 replacement 占位）
    - 302/307/header       -> 丢弃（这些是搜索引擎跳转/UA 改写，不是「解锁」，
                              合并进来会改变用户的搜索行为）
    - 误写进本段的脚本 URL -> 丢弃
    - 其他无法解析的       -> 丢弃并计数（绝不静默进产物）
    """
    t = line.strip()
    if re.match(r"^https?://\S+\.js$", t):
        stats["urw_script_url"] += 1
        return None
    m = re.match(r"^(.+?)\s+-\s+(reject[\w-]*|302|307|header)$", t)
    if m:
        pat, act = m.group(1), m.group(2)
    else:
        m = re.match(r"^(.+?)\s+(reject[\w-]*|302|307|header)$", t)
        if not m:
            stats["urw_bad"] += 1
            return None
        pat, act = m.group(1), m.group(2)
    if act not in ALLOW_ACTION:
        stats["urw_redirect_dropped"] += 1
        return None
    return pat + " " + act


def parse(path, out, stats):  # noqa: C901
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    for raw in lines:
        t = raw.strip()
        if not t:
            continue
        m = SEC_RE.match(t)
        if m:
            name = m.group(1).strip().lower()
            cur = name if name in KEEP else ("DROP" if name in DROP_SEC else None)
            if cur is None:
                stats["unknown_sections"].add(name)
            continue
        if cur is None or t.startswith("#"):
            continue
        if cur == "DROP":
            stats["dropped"] += 1
            continue

        if cur == "mitm":
            if "hostname" not in t.lower():
                continue
            v = t.split("=", 1)[1] if "=" in t else t
            v = re.sub(r"%APPEND%|%INSERT%", "", v, flags=re.I)
            for h in v.split(","):
                h = h.strip().lower()
                if not h or h.startswith("-"):      # SR 不支持负号排除
                    if h.startswith("-"):
                        stats["mitm_negated"].append(h)
                    continue
                if " " in h or "=" in h:
                    continue
                out["mitm"].append(h)
            stats["modules"] += 1
        elif cur == "script":
            line = clean_script(t)
            if "type=" not in line or "script-path=" not in line:
                conv = clean_legacy_script(line, stats["legacy_idx"], stats)
                if conv:
                    stats["legacy_idx"] += 1
                    out["script"].append(conv)
                else:
                    # 模块里的 /* */ 说明文字或无法识别的内容
                    stats["script_no_path"] += 1
                continue
            out["script"].append(line)
        elif cur == "url rewrite":
            c = clean_url_rewrite(t, stats)
            if c:
                out[cur].append(c)
        elif cur in ("rule", "map local"):
            out[cur].append(t)


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("srcdir")
    ap.add_argument("dst")
    ap.add_argument("--raw-url", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--filter", choices=["all", "unlock", "ad"], default="all",
                    help="只合并指定类别；unlock=解锁/破解，ad=纯去广告")
    a = ap.parse_args()

    files = sorted(f for f in os.listdir(a.srcdir) if f.endswith((".module", ".sgmodule")))
    out = {"rule": [], "url rewrite": [], "map local": [], "script": [], "mitm": []}

    stats = {"modules": 0, "dropped": 0, "script_no_path": 0,
             "mitm_negated": [], "unknown_sections": set(),
             "urw_script_url": 0, "urw_bad": 0, "urw_redirect_dropped": 0,
             "legacy_script_converted": 0, "legacy_idx": 0}

    if not files:
        raise SystemExit("ERROR: %s 里没有任何 .module/.sgmodule" % a.srcdir)

    picked, kinds = [], {"unlock": 0, "ad": 0, "other": 0}
    for f in files:
        path = os.path.join(a.srcdir, f)
        kind, _, _ = classify(path)
        kinds[kind] += 1
        if a.filter == "all" or kind == a.filter:
            picked.append(path)
    if not picked:
        raise SystemExit("ERROR: 过滤 %s 后没有模块（统计: %s）" % (a.filter, kinds))

    for path in picked:
        parse(path, out, stats)

    # 去重（保序）
    def dedupe(seq):
        seen, res = set(), []
        for x in seq:
            k = re.sub(r"\s+", " ", x).strip()
            if k not in seen:
                seen.add(k)
                res.append(x)
        return res

    if not out["script"] and not out["url rewrite"]:
        raise SystemExit("ERROR: 没解析出任何脚本/改写规则，疑似目录结构变化")
    rule = dedupe(out["rule"])
    urw = dedupe(out["url rewrite"])
    ml = dedupe(out["map local"])
    script = dedupe(out["script"])
    mitm = sorted({h for h in out["mitm"]}, key=str.lower)

    lines = []
    label = {"unlock": "解锁/破解", "ad": "去广告", "all": "全部"}[a.filter]
    title = "SR 去广告合集（deezertidal）" if a.filter == "ad" else "SR App 解锁合集（deezertidal）"
    lines.append("#!name=" + title)
    lines.append(
        "#!desc=由 deezertidal/shadowrocket-rules 的 %d 个单 App 模块（类别: %s）自动合并："
        "脚本 %d 条、URL Rewrite %d 条、MITM %d 个域名。Header Rewrite 已剔除（SR 不支持）。"
        % (len(picked), label, len(script), len(urw), len(mitm)))
    lines.append("#!author=deezertidal (modules) · sr-adblock (converter)")
    lines.append("#!system=ios")
    lines.append("#!category=工具")
    lines.append("#!tag=" + ("去广告" if a.filter == "ad" else "解锁"))
    if a.raw_url:
        lines.append("#!raw-url=" + a.raw_url)
    lines.append("")
    lines.append("# ============================================================")
    lines.append("#  合并统计: 模块 %d ｜ Rule %d ｜ URL Rewrite %d ｜ Script %d ｜ MITM %d"
                 % (len(picked), len(rule), len(urw), len(script), len(mitm)))
    lines.append("# ============================================================")
    lines.append("")

    def block(title, seq):
        if not seq:
            return
        lines.append("[%s]" % title)
        lines.extend(seq)
        lines.append("")

    block("Rule", rule)
    block("URL Rewrite", urw)
    block("Map Local", ml)
    block("Script", script)
    if mitm:
        lines.append("[MITM]")
        lines.append("hostname = " + ",".join(mitm))
        lines.append("")

    os.makedirs(os.path.dirname(os.path.abspath(a.dst)), exist_ok=True)
    with open(a.dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    rep = {"modules": len(picked), "filter": a.filter, "kinds": kinds, "rule": len(rule), "url_rewrite": len(urw),
           "map_local": len(ml), "script": len(script), "mitm": len(mitm),
           "dropped_lines": stats["dropped"], "script_without_path": stats["script_no_path"],
           "mitm_negated_ignored": len(stats["mitm_negated"]),
           "urw_script_url_dropped": stats["urw_script_url"],
           "urw_unparsable_dropped": stats["urw_bad"],
           "urw_redirect_dropped": stats["urw_redirect_dropped"],
           "legacy_script_converted": stats["legacy_script_converted"],
           "unknown_sections": sorted(stats["unknown_sections"]),
           "bytes": os.path.getsize(a.dst)}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
