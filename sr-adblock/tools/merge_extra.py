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
            t = TYPE_MAP.get(parts[0].lower())
            if not t:
                continue
            if len(parts) > 2 and "reject" not in parts[2].lower():
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

    added, skipped_dup, skipped_major = [], 0, []
    for src in args.source:
        for t, v in parse_source(src):
            if covered(t, v):
                skipped_dup += 1
                continue
            if (not args.allow_major and t in ("DOMAIN", "DOMAIN-SUFFIX")
                    and v.lower() in MAJOR):
                skipped_major.append(v)
                continue
            have.add((t, v))
            if t == "DOMAIN-SUFFIX":
                suffix.add(v.lower())
            added.append("%s,%s,REJECT" % (t, v))

    if added and rule_idx:
        pos = rule_idx[-1] + 1
        text = text[:pos] + added + text[pos:]

    with open(args.module, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(text))

    info = {"added": len(added), "skipped_duplicate": skipped_dup,
            "skipped_major_site": skipped_major}
    print(json.dumps(info, ensure_ascii=False, indent=1))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
