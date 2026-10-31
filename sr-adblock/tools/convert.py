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

import repair  # noqa: E402

# 范围过宽、误伤风险明确的规则（上游自带，转换期剔除并记入 report）
TOO_BROAD = {
    ("DOMAIN-KEYWORD", "trace.qq.com"),   # 关键词匹配任意位置，会命中非 QQ 域名的 URL 参数
    ("DOMAIN-SUFFIX", "l.qq.com"),        # 腾讯短链/日志全集，拦掉影响 QQ 内链接跳转
}

KEEP = ["Rule", "Host", "URL Rewrite", "Map Local", "Script", "MITM"]
DROP = ["Body Rewrite", "Header Rewrite", "General"]
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
    hosts, fixes = [], {}
    for line in eff(lines):
        if not line.lower().startswith("hostname"):
            continue
        val = line.split("=", 1)[1] if "=" in line else ""
        for h in val.split(","):
            h = h.strip()
            if not h:
                continue
            # Surge 的模块合并指令，SR 不认
            h, changed, _ = repair.fix_hostname(h)
            if changed:
                fixes["hostname 规范化"] = fixes.get("hostname 规范化", 0) + 1
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


# 上游 fmz200 知乎脚本含一个会导致脚本崩溃的 bug（item vs i），
# 由 tools/patch_zhihu.py 修补后托管在我们自己的仓库，规则改指向这份修补版。
UPSTREAM_ZHIHU = "https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/zhihu/zhihu.js"


def redirect_script_path(line, scripts_base):
    """把上游知乎脚本替换为本地托管的修补版，其余 script-path 不动"""
    if UPSTREAM_ZHIHU in line:
        return line.replace(UPSTREAM_ZHIHU, scripts_base + "zhihu.js")
    return line


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
        l2 = l
        if "data-type=file" in l2:
            dropped += 1
            continue
        if "data-type=tiny-gif" in l2:
            pat = l2.split("data-type=")[0].strip()
            extra_rw.append(pat + " reject-tinygif")
            continue
        kept_lines.append(l2)
    return kept_lines, extra_rw, dropped


def load_extra(path):
    """解析 tools/extra_rules.txt（支持 [Rule] / [Map Local] / [MITM] 分段）"""
    out, cur = {}, None
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1]
                out.setdefault(cur, [])
                continue
            if cur:
                out[cur].append(line)
    return out


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
    unknown_sections = {}
    for name, lines in sections:
        if name in DROP or name not in KEEP:
            dropped[name] = dropped.get(name, 0) + len(eff(lines))
            if name not in DROP:
                unknown_sections[name] = {"lines": len(eff(lines)), "sample": eff(lines)[:2]}

    report = {
        "source": os.path.basename(args.src),
        "source_date": meta.get("date", ""),
        "kept": {},
        "dropped": dropped,
        "notes": [],
        "unknown_sections": unknown_sections,
        "fixes": {},
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
    # 知乎脚本改指向本地修补版（上游版本有 item 未定义的崩溃 bug）
    if args.raw_url and "/dist/" in args.raw_url:
        _scripts_base = args.raw_url.rsplit("/dist/", 1)[0] + "/scripts/"
        _r = 0
        for _i, _l in enumerate(sc_clean):
            _n = redirect_script_path(_l, _scripts_base)
            if _n != _l:
                sc_clean[_i] = _n
                _r += 1
        if _r:
            report["fixes"]["知乎脚本重定向"] = _r
            report["notes"].append("知乎脚本改指向本地修补版 %d 条" % _r)
    report["kept"]["Script"] = len(sc_clean)
    sc_types = {}
    for l in sc_eff:
        m = re.search(r"type=([a-z-]+)", l)
        t = m.group(1) if m else "?"
        sc_types[t] = sc_types.get(t, 0) + 1
    report["kept"]["Script.types"] = sc_types

    # MITM
    extra_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "extra_rules.txt")
    extra = load_extra(extra_path)
    hosts = build_mitm(kept.get("MITM", []))
    # 补充规则里声明的 MITM 域名（URL-REGEX 规则必须靠它才看得到完整 URL）
    extra_mitm = [h for h in extra.get("MITM", []) if h and h.lower() not in {x.lower() for x in hosts}]
    if extra_mitm:
        hosts = hosts + extra_mitm
        report["fixes"]["本地补充(MITM)"] = len(extra_mitm)
        report["notes"].append("本地补充 [MITM] %d 个域名" % len(extra_mitm))
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

    # 上游 URL 协议笔误（http:// / http?:）统一放宽为 https?://
    fixed_n = 0
    def _fix(lines):
        nonlocal fixed_n
        out = []
        for l in lines:
            nl, changed, _ = repair.fix_scheme(l)
            if changed:
                fixed_n += 1
            out.append(nl)
        return out
    rule_lines = _fix(rule_lines)
    misplaced = 0
    fixed_rules = []
    for l in rule_lines:
        nl, ch = repair.fix_misplaced_action(l)
        if ch:
            misplaced += 1
        fixed_rules.append(nl)
    rule_lines = fixed_rules
    broad_dropped = []
    kept_rules = []
    for l in rule_lines:
        parts = [x.strip() for x in l.split(",")]
        if len(parts) >= 2 and (parts[0], parts[1]) in TOO_BROAD:
            broad_dropped.append(l)
            continue
        kept_rules.append(l)
    rule_lines = kept_rules

    # 去重：上游本身有 147 行重复；合并后又带入若干；动作错位修复也会产生同域名双动作
    simple_types = ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "IP-CIDR6")
    pri = {"REJECT-NO-DROP": 3, "REJECT-DROP": 2, "REJECT": 1}
    seen, uniq = set(), []
    for l in rule_lines:
        st = l.strip()
        if not st or st.startswith("#"):     # 注释与空行不参与去重
            uniq.append(l)
            continue
        if st in seen:
            continue
        seen.add(st)
        uniq.append(l)
    exact_dup = sum(1 for l in rule_lines if l.strip() and not l.strip().startswith("#")) - len(seen)

    best = {}
    for i, l in enumerate(uniq):
        p = [x.strip() for x in l.split(",")]
        if len(p) >= 3 and p[0] in simple_types:
            k = (p[0], p[1])
            if k not in best or pri.get(p[2], 0) > pri.get(best[k][0], 0):
                best[k] = (p[2], i)
    keep = {i for _, i in best.values()}
    final = []
    for i, l in enumerate(uniq):
        p = [x.strip() for x in l.split(",")]
        if len(p) >= 3 and p[0] in simple_types and i not in keep:
            continue
        final.append(l)
    action_dup = len(uniq) - len(final)
    rule_lines = final

    # 本地补充规则（tools/extra_rules.txt），不随上游覆盖；支持 [Rule] / [Map Local] 分段
    if extra.get("Rule"):
        front = [l for l in extra["Rule"] if l not in seen]
        if front:
            # 必须放最前：父域常被判 DIRECT，Rule 顺序匹配下放末尾永远轮不到
            rule_lines = front + rule_lines
            seen.update(front)
            report["fixes"]["本地补充(Rule)"] = len(front)
            report["notes"].append("本地补充 [Rule] %d 条已置顶（避免被父域 DIRECT 抢先）" % len(front))
    if exact_dup or action_dup:
        report["fixes"]["规则去重"] = exact_dup + action_dup
        report["notes"].append("规则去重 %d 条（完全相同 %d / 同域名多动作 %d）"
                               % (exact_dup + action_dup, exact_dup, action_dup))
    if broad_dropped:
        report["dropped"]["过宽规则"] = len(broad_dropped)
        report["notes"].append("剔除范围过宽规则 %d 条: %s"
                               % (len(broad_dropped), ", ".join(broad_dropped)))
    if misplaced:
        report["fixes"]["动作后缀错位"] = misplaced
        report["notes"].append("动作后缀错位修正 %d 条（xxx-NO-DROP -> REJECT-NO-DROP）" % misplaced)
    urw = _fix(urw)
    ml_clean = _fix(ml_clean)
    if fixed_n:
        report["notes"].append("URL 协议笔误修正 %d 条（http:// 或 http?: -> https?://）" % fixed_n)
        report["fixes"]["协议笔误"] = fixed_n

    def dedupe_lines(lines):
        seen, out, removed = set(), [], 0
        for l in lines:
            st = l.strip()
            if not st or st.startswith("#"):
                out.append(l)
                continue
            if st in seen:
                removed += 1
                continue
            seen.add(st)
            out.append(l)
        return out, removed

    url_rewrite = [l for l in urw]
    map_local = [l for l in ml_clean]
    if extra.get("Map Local"):
        # 置顶：Map Local 同样按顺序匹配，追加到末尾会被上游同 URL 的规则抢先
        map_local = extra["Map Local"] + map_local
        report["fixes"]["本地补充(Map Local)"] = len(extra["Map Local"])
        report["notes"].append("并入本地补充 [Map Local] %d 条" % len(extra["Map Local"]))
    scripts = [l for l in sc_clean]
    if extra.get("Script"):
        # 置顶：我们的增强脚本要优先于上游同名 pattern 的脚本
        scripts = extra["Script"] + scripts
        report["fixes"]["本地补充(Script)"] = len(extra["Script"])
        report["notes"].append("本地补充 [Script] %d 条（置顶）" % len(extra["Script"]))
    extra_dropped = 0
    url_rewrite, d1 = dedupe_lines(url_rewrite)
    map_local, d2 = dedupe_lines(map_local)
    scripts, d3 = dedupe_lines(scripts)
    extra_dropped = d1 + d2 + d3
    if extra_dropped:
        report["fixes"]["其它段去重"] = extra_dropped
        report["notes"].append("URL Rewrite/Map Local/Script 去重 %d 条（%d/%d/%d）"
                               % (extra_dropped, d1, d2, d3))

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
    block("URL Rewrite", url_rewrite)
    block("Map Local", map_local)
    block("Script", scripts)
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
