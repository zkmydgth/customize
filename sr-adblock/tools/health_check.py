#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产物健康检查（跑在提交之前）。

四项：
  1. 正则编译 —— 所有 pattern 交给 JS 引擎编译；`(?>...)` 这类不支持的会红
  2. MITM 合法性 —— 无负号、无 :0 端口、无空格、无重复
  3. Rule 顺序冲突 —— 具体规则被更宽的 DIRECT 规则抢先覆盖
  4. 脚本 URL 抽样可达性（--network，默认关闭；404 只警告不阻断）

退出码：1 = 有硬失败（正则编译失败 / MITM 非法）
用法:
  python3 tools/health_check.py --module dist/blockAds.sr.module
  python3 tools/health_check.py --module dist/unlock.srmodule --network
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

SEC_RE = re.compile(r"^\[([^\]]+)\]\s*$")
# JS 支持但需要 flag 的语法，编译失败时不判为硬错误
SOFT_SYNTAX = ("(?<", "\\p{", "\\P{")


def parse(path):
    secs, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            t = line.rstrip("\n")
            m = SEC_RE.match(t.strip())
            if m:
                cur = m.group(1).strip()
                secs.setdefault(cur, [])
                continue
            if cur and t.strip() and not t.strip().startswith("#"):
                secs[cur].append(t.strip())
    return secs


def collect_patterns(secs):
    out = []
    for l in secs.get("URL Rewrite", []):
        m = re.match(r"^(.+?)\s+\S+$", l)
        if m:
            out.append(("URL Rewrite", m.group(1)))
    for l in secs.get("Map Local", []):
        m = re.match(r"^(\S+)\s", l)
        if m:
            out.append(("Map Local", m.group(1)))
    for l in secs.get("Script", []):
        m = re.search(r"\bpattern=([^,]+)", l)
        if m:
            out.append(("Script", m.group(1).strip()))
    return out


def check_regex(pats):
    """交给 node 编译，返回 (硬失败, 软警告)"""
    if not pats:
        return [], []
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(pats, f, ensure_ascii=False)
        tmp = f.name
    js = r"""
const fs=require('fs');
const pats=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const hard=[], soft=[];
for (const [sec,p] of pats) {
  let q=p, flags='';
  if (/\(\?i\)/.test(q)) { flags='i'; q=q.replace(/\(\?i\)/g,''); }
  try { new RegExp(q, flags); }
  catch(e) {
    const softish = /\(\?</.test(p) || /\\[pP]\{/.test(p);
    (softish?soft:hard).push([sec,p.slice(0,110),e.message.slice(0,60)]);
  }
}
console.log(JSON.stringify({hard,soft}));
"""
    try:
        r = subprocess.run(["node", "-e", js, tmp], capture_output=True, text=True, timeout=120)
        os.unlink(tmp)
        if r.returncode != 0:
            return [["node", "执行失败", r.stderr[:200]]], []
        d = json.loads(r.stdout)
        return d["hard"], d["soft"]
    except Exception as e:
        import contextlib
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        return [["node", "调用异常", str(e)[:120]]], []


def check_mitm(secs):  # noqa: C901
    hosts = []
    for l in secs.get("MITM", []):
        if l.lower().startswith("hostname") and "=" in l:
            for h in l.split("=", 1)[1].split(","):
                h = re.sub(r"^%(APPEND|INSERT)%\s*", "", h.strip(), flags=re.I)
                if h:
                    hosts.append(h)
    errs = []
    if not hosts:
        return errs, 0
    low = [h.lower() for h in hosts]
    if len(set(low)) != len(low):
        errs.append("MITM 有重复域名 %d 个" % (len(low) - len(set(low))))
    if any(" " in h for h in hosts):
        errs.append("MITM 含空格")
    if any(h.startswith("-") for h in hosts):
        errs.append("MITM 含 - 排除项")
    if any("%" in h for h in hosts):
        errs.append("MITM 含 %APPEND%/%INSERT%")
    if any(re.search(r":0$", h) for h in hosts):
        errs.append("MITM 含 :0 端口")
    return errs, len(hosts)


def check_rule_order(secs):
    """具体规则被更宽的 DIRECT/PROXY 规则抢先（顺序在前才会生效）"""
    rules = secs.get("Rule", [])
    pos = {}
    for i, r in enumerate(rules):
        p = r.split(",")
        if len(p) >= 3 and p[0] in ("DOMAIN", "DOMAIN-SUFFIX"):
            pos.setdefault((p[0], p[1].lower()), i)
    suffix_direct = {}
    for i, r in enumerate(rules):
        p = r.split(",")
        if len(p) >= 3 and p[0] == "DOMAIN-SUFFIX" and p[2] in ("DIRECT", "PROXY"):
            suffix_direct[p[1].lower()] = i
    conflicts = []
    for i, r in enumerate(rules):
        p = r.split(",")
        if len(p) < 3 or p[0] != "DOMAIN" or "REJECT" not in p[2]:
            continue
        h = p[1].lower()
        for s, si in suffix_direct.items():
            if h.endswith("." + s) and si < i:
                conflicts.append((h, s, i, si))
                break
    return conflicts


def check_mitm_coverage(secs):  # noqa: C901
    """规则引用的域名是否都在 MITM 里。

    URL Rewrite / Map Local / Script 都必须先解密才能看到完整 URL，
    域名不在 MITM → 规则永远匹配不到（2026-11-07 豆瓣 frodo.douban.com 即此因）。
    """
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import repair

    enabled = set()
    for l in secs.get("MITM", []):
        if l.lower().startswith("hostname") and "=" in l:
            for h in l.split("=", 1)[1].split(","):
                h = re.sub(r"^%(APPEND|INSERT)%\s*", "", h.strip(), flags=re.I)
                if h:
                    enabled.add(h.lower())

    def covered(h):
        h = h.lower()
        if h in enabled:
            return True
        for e in enabled:
            if e.startswith("*.") and h.endswith(e[1:]):
                return True
            if e.startswith("*") and h.endswith(e[1:]):
                return True
        return False

    checks = []
    for l in secs.get("URL Rewrite", []):
        m = re.match(r"^(.+?)\s+\S+$", l)
        if m:
            checks.append(("URL Rewrite", m.group(1)))
    for l in secs.get("Map Local", []):
        m = re.match(r"^(\S+)\s", l)
        if m:
            checks.append(("Map Local", m.group(1)))
    for l in secs.get("Script", []):
        m = re.search(r"\bpattern=([^,]+)", l)
        if m:
            checks.append(("Script", m.group(1)))

    missing = {}
    for sec, pat in checks:
        for h in repair.hosts_of_pattern(pat):
            if not covered(h):
                missing.setdefault(h.lower(), sec)
    return missing


def check_script_urls(secs, n=10):
    urls = []
    for l in secs.get("Script", []):
        m = re.search(r"script-path=(https?://[^,\s]+)", l)
        if m:
            urls.append(m.group(1))
    if not urls:
        return [], 0
    sample = urls[:n]
    bad = []
    for u in sample:
        r = subprocess.run(["curl", "-sS", "--http1.1", "--max-time", "12",
                            "-o", "/dev/null", "-w", "%{http_code}", u],
                           capture_output=True, text=True)
        code = (r.stdout or "").strip()
        if code in ("404", "410"):
            bad.append((code, u))
    return bad, len(sample)


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--network", action="store_true", help="抽样检查脚本 URL 可达性")
    ap.add_argument("--sample", type=int, default=10)
    a = ap.parse_args()

    if not os.path.exists(a.module):
        print("HEALTH FAIL: 找不到 %s" % a.module)
        return 1

    secs = parse(a.module)
    hard, soft = check_regex(collect_patterns(secs))
    mitm_errs, mitm_n = check_mitm(secs)
    order = check_rule_order(secs)
    dormant = check_mitm_coverage(secs)
    net_bad, net_n = ([], 0)
    if a.network:
        net_bad, net_n = check_script_urls(secs, a.sample)

    print("HEALTH %s: 正则 %d 条 | MITM %d | Rule %d"
          % (os.path.basename(a.module), len(collect_patterns(secs)), mitm_n, len(secs.get("Rule", []))))

    fail = False
    if hard:
        fail = True
        print("  ✗ 正则可编译失败 %d 条:" % len(hard))
        for sec, p, m in hard[:5]:
            print("     [%s] %s | %s" % (sec, p, m))
    if mitm_errs:
        fail = True
        for e in mitm_errs:
            print("  ✗", e)
    if dormant:
        print("  ! 被规则引用但不在 MITM 的域名 %d 个（这些规则匹配不到完整 URL）:" % len(dormant))
        for h, sec in list(dormant.items())[:6]:
            print("     %-34s ← [%s]" % (h, sec))
    if soft:
        print("  ! 需 flag 的语法 %d 条（不判失败）:" % len(soft))
        for sec, p, _m in soft[:3]:
            print("     [%s] %s" % (sec, p))
    if order:
        print("  ! Rule 顺序问题 %d 处（具体规则被更宽的 DIRECT 抢先）:" % len(order))
        for h, s, i, si in order[:3]:
            print("     %s:REJECT(第%d行) 被 %s:DIRECT(第%d行) 覆盖" % (h, i + 1, s, si + 1))
    if net_n:
        if net_bad:
            print("  ! 脚本 404/410 %d/%d（上游删了仓库，规则仍在 → 该功能失效）:" % (len(net_bad), net_n))
            for c, u in net_bad[:3]:
                print("     %s %s" % (c, u[:100]))
        else:
            print("  ✓ 脚本抽样 %d 条全部可达" % net_n)

    print("HEALTH %s" % ("FAIL" if fail else "PASS"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
