#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""额外规则合并器（来自上游其他规则集，如 QuantumultX/filter/filter.list）。

流程：解析 -> 标准化为 SR 语法 -> 与现有 Rule 去重（含后缀覆盖）-> 风险过滤 -> 插入

去重口径（重要）：
  - 精确同值同类型 -> 丢弃
  - 候选的域名已被现有 DOMAIN-SUFFIX 覆盖（candidate 以该后缀结尾）-> 丢弃
  - 现有的 DOMAIN 已被候选 DOMAIN-SUFFIX 覆盖 -> 丢弃候选（避免重复表达）

风险闸门：
  候选域名若是「知名主站本身」，默认不并入（拦掉整个站点 = 用户打不开 App/网页），
  但主站旗下的广告子域（ad.qq.com 之类）不受影响。
"""
import argparse
import json
import re

# Quantumult X / Clash 常见类型 -> Shadowrocket
TYPE_MAP = {
    "host-suffix": "DOMAIN-SUFFIX", "host": "DOMAIN", "host-keyword": "DOMAIN-KEYWORD",
    "ip-cidr": "IP-CIDR", "ip6-cidr": "IP-CIDR6", "domain": "DOMAIN",
    "domain-suffix": "DOMAIN-SUFFIX", "domain-keyword": "DOMAIN-KEYWORD",
}

# 知名主站：拦掉「本体」会让整个服务不可用，默认跳过
MAJOR = {
    "temu.com", "qq.com", "baidu.com", "taobao.com", "tmall.com", "jd.com", "bilibili.com",
    "weibo.com", "zhihu.com", "xiaohongshu.com", "douyin.com", "kuaishou.com", "meituan.com",
    "pinduoduo.com", "alipay.com", "163.com", "sina.com.cn", "sohu.com", "iqiyi.com",
    "youku.com", "aliyun.com", "tencent.com", "bytedance.com", "google.com", "apple.com",
    "microsoft.com", "amazon.com", "ebay.com", "netflix.com", "x.com", "twitter.com",
    "instagram.com", "facebook.com", "tiktok.com", "youtube.com", "whatsapp.com",
}


# 范围过宽：DOMAIN-SUFFIX 会拦掉整片子域、DOMAIN-KEYWORD 会匹配任意包含该串的 URL
TOO_BROAD = {"l.qq.com", "trace.qq.com"}

# 确定误伤：不是广告，而是 App 的 DNS/网络基础服务，拦掉会影响正常功能。
# 2026-10-31 从代理日志发现：增强版拦了 dns.weixin.qq.com.cn 84 次（微信 MMTLS），
# 来源是 217heidai 规则集把微信 DNS 误标成广告。
MERGE_DENY = {
    "dns.weixin.qq.com", "dns.weixin.qq.com.cn", "aedns.weixin.qq.com",
    "httpdns.alicdn.com", "httpdns.baidu.com", "httpdns.meituan.com",
}


def parse_source(path):
    """解析 QX/Clash 风格规则文件 -> [(TYPE, value)]"""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            raw_type = parts[0]
            if raw_type.upper() in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD",
                                    "IP-CIDR", "IP-CIDR6"):
                t = raw_type.upper()          # 已经是 SR/Surge 语法
                action = parts[2] if len(parts) > 2 else "REJECT"
            else:
                t = TYPE_MAP.get(raw_type.lower())
                if not t:
                    continue
                action = parts[2] if len(parts) > 2 else "reject"
            if "reject" not in action.lower():
                continue
            out.append((t, parts[1]))
    return out


def parse_rule_line(line):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--source", action="append", default=[], help="额外规则文件，可多次指定")
    ap.add_argument("--report", default="")
    ap.add_argument("--allow-major", action="store_true", help="不跳过知名主站（不推荐）")
    ap.add_argument("--min-len", type=int, default=0,
                    help="排除长度<=N 且只有两段的域名（防误伤），0=不过滤")
    ap.add_argument("--action", default="REJECT", help="统一动作（默认 REJECT）")
    ap.add_argument("--set-name", default="", help="改写 #!name=")
    ap.add_argument("--set-raw-url", default="", help="改写 #!raw-url=")
    args = ap.parse_args()

    with open(args.module, encoding="utf-8") as f:
        text = f.read().split("\n")
    sec, rule_idx = None, []
    existing = []
    for i, l in enumerate(text):
        m = re.match(r"^\[([^\]]+)\]$", l.strip())
        if m:
            sec = m.group(1)
            continue
        if sec == "Rule" and l.strip() and not l.lstrip().startswith("#"):
            rule_idx.append(i)
            r = parse_rule_line(l)
            if r:
                existing.append(r)

    have = set(existing)
    suffix = {v.lower() for t, v in existing if t == "DOMAIN-SUFFIX"}

    def covered(t, v):
        vl = v.lower()
        if (t, v) in have:
            return True
        return (t in ("DOMAIN", "DOMAIN-SUFFIX")
                and any(vl == s or vl.endswith("." + s) for s in suffix))

    added, skipped_dup, skipped_major, skipped_broad, skipped_short = [], 0, [], [], []
    for src in args.source:
        for t, v in parse_source(src):
            if covered(t, v):
                skipped_dup += 1
                continue
            if args.min_len and t in ("DOMAIN", "DOMAIN-SUFFIX") \
                    and len(v) <= args.min_len and v.count(".") == 1:
                skipped_short.append(v)
                continue
            if t in ("DOMAIN-SUFFIX", "DOMAIN-KEYWORD") and v.lower() in TOO_BROAD:
                skipped_broad.append(v)
                continue
            if v.lower() in MERGE_DENY:
                skipped_broad.append(v)
                continue
            if (not args.allow_major and t in ("DOMAIN", "DOMAIN-SUFFIX")
                    and v.lower() in MAJOR):
                skipped_major.append(v)
                continue
            have.add((t, v))
            if t == "DOMAIN-SUFFIX":
                suffix.add(v.lower())
            added.append("%s,%s,%s" % (t, v, args.action))

    if args.set_name or args.set_raw_url:
        for i, line in enumerate(text):
            # 容忍 BOM：带 BOM 的模块用 startswith 判断会静默不生效
            bare = line.lstrip("\ufeff")
            if args.set_name and bare.startswith("#!name="):
                text[i] = "#!name=" + args.set_name
            if args.set_raw_url and bare.startswith("#!raw-url="):
                text[i] = "#!raw-url=" + args.set_raw_url

    if added and rule_idx:
        # 顺序：本地补充（最优先）→ 本步骤合并的规则 → 上游。
        # 插在 __LOCAL_EXTRA_END__ 标记之后；没有标记（无本地补充）时插段首。
        marker = next((i for i, l in enumerate(text)
                       if l.strip() == "# __LOCAL_EXTRA_END__"), None)
        pos = (marker + 1) if marker is not None else rule_idx[0]
        text = text[:pos] + added + text[pos:]

    # 合并会改变 Rule 条数，头部统计行要跟着更新（否则与实际不符）
    def _counts(lines):
        d, cur = {}, None
        for l in lines:
            t = l.strip()
            if t.startswith("[") and t.endswith("]"):
                cur, d[cur] = t[1:-1], 0
                continue
            if cur and t and not t.startswith("#"):
                d[cur] += 1
        return d
    c = _counts(text)
    mitm_n = 0
    for l in text:
        if l.strip().lower().startswith("hostname") and "=" in l:
            mitm_n = len([h for h in l.split("=", 1)[1].split(",") if h.strip()])
    for i, l in enumerate(text):
        if l.startswith("#  保留统计:"):
            text[i] = ("#  保留统计: Rule %d / URL Rewrite %d / Map Local %d / Script %d / MITM %d hosts"
                       % (c.get("Rule", 0), c.get("URL Rewrite", 0), c.get("Map Local", 0),
                          c.get("Script", 0), mitm_n))

    with open(args.module, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(text))

    info = {"added": len(added), "skipped_duplicate": skipped_dup,
            "skipped_major_site": skipped_major, "skipped_too_broad": skipped_broad,
            "skipped_short": len(skipped_short)}
    print(json.dumps(info, ensure_ascii=False, indent=1))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
