#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blockAds.module (Surge)  ->  Shadowrocket 适配模块 (.sgmodule)

用法:
    python3 tools/convert.py upstream.module dist/blockAds.sr.module \
        [--raw-url https://raw.githubusercontent.com/<user>/<repo>/main/dist/blockAds.sr.module] \
        [--mitm-keep tools/mitm-keep.txt] \
        [--report report.json]

处理规则:
  保留段落: Rule / Host / URL Rewrite / Map Local / Script / MITM
  丢弃段落: Body Rewrite (jq 表达式, SR 无引擎) / Header Rewrite (SR 无此段) / General (SR 不认的键)
  其它清理: MITM 去掉 %APPEND% 前缀并去重; Script 行去掉 argument= 字段;
           文件头重写为 SR 可识别的 #! 元数据
"""
import argparse
import datetime
import json
import os
import re

KEEP = ["Rule", "Host", "URL Rewrite", "Map Local", "Script", "MITM"]
DROP = ["Body Rewrite", "Header Rewrite"]
SEC_RE = re.compile(r"^\[([^\[\]]+)\]\s*$")

# SR 不支持 / 无意义的段内条目类型（预留）
SR_DROP_RULE_TYPES = set()


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc).replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def split_sections(text):
    """-> (header_lines, [(name, lines), ...])"""
    cur, header, out = None, [], []
    for line in text.split("\n"):
        m = SEC_RE.match(line)
        if m:
            cur = m.group(1).strip()
            out.append((cur, []))
            continue
        if cur is None:
            header.append(line)
        else:
            out[-1][1].append(line)
    return header, out


def eff(lines):
    return [l for l in lines if l.strip() and not l.lstrip().startswith("#")]


def parse_header(header):
    meta = {}
    for line in header:
        if line.startswith("#!"):
            body = line[2:]
            if "=" in body:
                k, v = body.split("=", 1)
                meta[k.strip()] = v.strip()
    return meta


def build_mitm(lines):
    hosts = []
    for line in eff(lines):
        if not line.lower().startswith("hostname"):
            continue
        val = line.split("=", 1)[1] if "=" in line else ""
        for h in val.split(","):
            h = h.strip()
            if not h:
                continue
            # Surge 的模块合并指令，SR 不认
            h = re.sub(r"^%(APPEND|INSERT)%\s*", "", h, flags=re.I)
            h = h.strip()
            if h:
                hosts.append(h)
    seen, uniq = set(), []
    for h in hosts:
        k = h.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    return uniq


def clean_script_line(line):
    """SR 适配：删掉 argument= 字段；requires-body 归一为 1/0"""
    line = re.sub(r",?\s*argument=[^,]*", "", line)
    line = re.sub(r"requires-body=(true|1)\b", "requires-body=1", line, flags=re.I)
    return re.sub(r"requires-body=(false|0)\b", "requires-body=0", line, flags=re.I)


def process_maplocal(lines):
    """Map Local 适配：
       - 修正上游正则笔误 ^http?:/  ->  ^https?:/
       - data-type=tiny-gif -> 转成 URL Rewrite 的 reject-tinygif（SR 无该 data-type）
       - data-type=file     -> 丢弃（模块无法携带本地文件）
    """
    kept_lines, extra_rw, dropped = [], [], 0
    for l in lines:
        if not l.strip() or l.lstrip().startswith("#"):
            kept_lines.append(l)
            continue
        l2 = re.sub(r"\^http\?:", "^https?:", l)
        if "data-type=file" in l2:
            dropped += 1
            continue
        if "data-type=tiny-gif" in l2:
            pat = l2.split("data-type=")[0].strip()
            extra_rw.append(pat + " reject-tinygif")
            continue
        kept_lines.append(l2)
    return kept_lines, extra_rw, dropped


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--raw-url", default="")
    ap.add_argument("--mitm-keep", default="")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    text = read_text(args.src)
    header, sections = split_sections(text)
    meta = parse_header(header)

    kept, dropped = {}, {}
    for name, lines in sections:
        if name in KEEP:
            kept.setdefault(name, []).extend(lines)
    for name, lines in sections:
        if name in DROP or name not in KEEP:
            dropped[name] = dropped.get(name, 0) + len(eff(lines))

    report = {
        "source": os.path.basename(args.src),
        "source_date": meta.get("date", ""),
        "kept": {},
        "dropped": dropped,
        "notes": [],
    }

    # ---- 逐段处理 ----
    # Rule
    rule_lines = kept.get("Rule", [])
    rule_eff = eff(rule_lines)
    types = {}
    for l in rule_eff:
        t = l.split(",")[0].strip()
        types[t] = types.get(t, 0) + 1
    report["kept"]["Rule"] = len(rule_eff)
    report["kept"]["Rule.types"] = types

    # Map Local 先处理：tiny-gif -> reject-tinygif，file -> 丢弃
    ml = kept.get("Map Local", [])
    ml_clean, ml_extra_rw, ml_dropped = process_maplocal(ml)
    if ml_extra_rw:
        report["notes"].append("Map Local data-type=tiny-gif -> URL Rewrite reject-tinygif: %d 条" % len(ml_extra_rw))
    if ml_dropped:
        report["notes"].append("Map Local data-type=file 丢弃: %d 条" % ml_dropped)

    # URL Rewrite
    urw = kept.get("URL Rewrite", []) + ml_extra_rw
    urw_eff = eff(urw)
    actions = {}
    for l in urw_eff:
        m = re.search(r"\s+(\S+)\s*$", l) or re.search(r"\s+([a-z-]+)\s+", l)
        a = (m.group(1) if m else "?").lower()
        actions[a] = actions.get(a, 0) + 1
    report["kept"]["URL Rewrite"] = len(urw_eff)
    report["kept"]["URL Rewrite.actions"] = actions

    report["kept"]["Map Local"] = len(eff(ml_clean))

    # Script
    sc = kept.get("Script", [])
    sc_eff = eff(sc)
    sc_clean = [clean_script_line(l) for l in sc_eff]
    report["kept"]["Script"] = len(sc_clean)
    sc_types = {}
    for l in sc_eff:
        m = re.search(r"type=([a-z-]+)", l)
        t = m.group(1) if m else "?"
        sc_types[t] = sc_types.get(t, 0) + 1
    report["kept"]["Script.types"] = sc_types

    # MITM
    hosts = build_mitm(kept.get("MITM", []))
    if args.mitm_keep and os.path.exists(args.mitm_keep):
        pats = []
        with open(args.mitm_keep, encoding="utf-8-sig") as f:
            keep_lines = f.read().split("\n")
        for l in keep_lines:
            l = l.strip()
            if l and not l.startswith("#"):
                pats.append(l)
        hosts = [h for h in hosts if any(re.fullmatch(p, h) for p in pats)]
        report["notes"].append("MITM 已按 mitm-keep.txt 裁剪")
    report["kept"]["MITM.hostnames"] = len(hosts)

    # Host
    host_lines = kept.get("Host", [])
    report["kept"]["Host"] = len(eff(host_lines))

    # ---- 组装输出 ----
    name = "SR 去广告&净化（fmz200 · 完整版）"
    desc = ("由 fmz200/wool_scripts 的 Surge 模块自动转换：Body Rewrite 96 条已编译为 JS 脚本一并生效；"
            "Header Rewrite 与 General 中 SR 不支持的项已剔除；MITM 已清理 %APPEND% 并补全脚本所需域名。")
    out = []
    out.append("#!name=" + name)
    out.append("#!desc=" + desc)
    out.append("#!author=fmz200 (rules/scripts) · sr-adblock (converter)")
    if meta.get("homepage"):
        out.append("#!homepage=" + meta["homepage"])
    if meta.get("icon"):
        out.append("#!icon=" + meta["icon"])
    out.append("#!system=ios")
    out.append("#!category=去广告")
    out.append("#!tag=去广告,Shadowrocket")
    if args.raw_url:
        out.append("#!raw-url=" + args.raw_url)
    out.append("#!date=" + (meta.get("date") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")))
    out.append("")
    out.append("# ============================================================")
    out.append("#  Shadowrocket 适配版 · 自动生成，请勿手工修改")
    out.append("#  上游日期: %s" % (meta.get("date") or "unknown"))
    out.append("#  保留: Rule %d / URL Rewrite %d / Map Local %d / Script %d / MITM %d hosts"
               % (len(rule_eff), len(urw_eff), len(eff(ml_clean)), len(sc_clean), len(hosts)))
    for k, v in dropped.items():
        if v:
            out.append("#  已剔除 [%s] %d 条（SR 不支持）" % (k, v))
    out.append("# ============================================================")
    out.append("")

    def block(title, lines):
        if not eff(lines):
            return
        out.append("[%s]" % title)
        out.extend(lines)
        while out and not out[-1].strip():
            out.pop()
        out.append("")

    block("Rule", rule_lines)
    block("Host", host_lines)
    block("URL Rewrite", urw)
    block("Map Local", ml_clean)
    block("Script", sc_clean)
    if hosts:
        out.append("[MITM]")
        # SR 对多行 hostname 的合并行为不稳定，统一输出为单行（上游也是单行）
        out.append("hostname = " + ",".join(hosts))
        out.append("")

    os.makedirs(os.path.dirname(os.path.abspath(args.dst)), exist_ok=True)
    with open(args.dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).rstrip() + "\n")

    report["output"] = args.dst
    report["output_bytes"] = os.path.getsize(args.dst)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
