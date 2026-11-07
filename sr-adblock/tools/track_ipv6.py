#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跟踪知乎的 IPv6 网段，自动生成 IP-CIDR6 屏蔽规则。

背景：知乎 App 拿到 AAAA 后会直连 IPv6，此时 Shadowrocket 只看到 IP、
无法按域名解密，Map Local 与 Script 全部失效。因此需要在 IP 层拦掉它。

两条命令分开，因为**采样必须在设备侧**：
  CDN 就近调度，海外 DNS 查到的段（如 240d:c010::/32）与国内完全不同，
  GitHub Actions 在海外跑采样没有意义。

用法：
  # 在设备上采样（iSH / 本地，需能解析国内 CDN）
  python3 tools/track_ipv6.py --sample

  # 在 CI 上构建（不联网，只读 state + 过期清理）
  python3 tools/track_ipv6.py --build

输出：tools/ipv6-auto.txt（供 convert.py 并入产物）
"""
import argparse
import datetime
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(HERE, "ipv6-state.json")
OUT = os.path.join(HERE, "ipv6-auto.txt")

# 需要屏蔽的 App 域名（知乎）
TARGETS = [
    "api.zhihu.com", "appcloud2.zhihu.com", "www.zhihu.com",
    "m-cloud.zhihu.com", "picx.zhimg.com", "duga.zhihu.com",
    "zhuanlan.zhihu.com", "page-info.zhihu.com",
]
# 不能误伤的域名（微信文件传输等）
PROTECT = [
    "szfilehelper.weixin.qq.com", "filehelper.weixin.qq.com",
    "dldir1.qq.com", "vweixinf.tc.qq.com", "short.weixin.qq.com",
]
DOH = "https://dns.alidns.com/resolve?name=%s&type=AAAA"
KEEP_DAYS = 7          # 多少天没出现就删除
MIN_PREFIX = 48        # 只接受 /48 更细的段（/32 覆盖过广，易误伤）


def resolve(name, rnd=0):
    req = urllib.request.Request(DOH % name + ("&rnd=%d" % rnd if rnd else ""),
                                 headers={"User-Agent": "sr-adblock-track"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    return [x["data"] for x in d.get("Answer", []) if x.get("type") == 28]


def prefix_of(addr, bits):
    """把 IPv6 地址截断到 /bits 前缀"""
    groups = addr.split(":")
    if len(groups) != 8:
        groups = (groups + ["0"] * 8)[:8]
    nums = [int(g, 16) if g else 0 for g in groups]
    keep = bits // 16
    out = nums[:keep] + [0] * (8 - keep)
    # 压缩末尾的 0 组，输出规范形式（240e:97c:39:f80::/64 而不是 ...:0:0:0:0::/64）
    shown = out[:]
    while shown and shown[-1] == 0:
        shown.pop()
    body = ":".join("%x" % n for n in shown)
    return (body + "::/%d" % bits) if body else "::/%d" % bits


def _g64(prefix):
    """取前缀的前 4 组（/64 粒度），用于判断是否与受保护域名重叠"""
    body = prefix.split("/")[0].rstrip(":")
    return ":".join((body.split(":") + ["0"] * 4)[:4])


def _collides(p, protect_nets):
    g = _g64(p)
    return any(_g64(x) == g for x in protect_nets)


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1, sort_keys=True)


def cmd_sample(args):  # noqa: C901
    st = load_state()
    today = datetime.date.today().isoformat()

    # 先收集受保护域名的网段，用于排除
    protect_nets = set()
    for d in PROTECT:
        try:
            for a in resolve(d):
                protect_nets.add(prefix_of(a, 48))
        except Exception as e:  # noqa: BLE001
            print("  警告: 解析 %s 失败 %s" % (d, e), file=sys.stderr)

    found = set()
    for d in TARGETS:
        for rnd in (0, 1, 2):
            try:
                for a in resolve(d, rnd):
                    found.add(prefix_of(a, 64))
            except Exception:  # noqa: BLE001
                continue

    added, skipped = [], []
    for p in sorted(found):
        bits = int(p.rsplit("/", 1)[1])
        if bits < MIN_PREFIX:
            skipped.append((p, "段过宽"))
            continue
        if _collides(p, protect_nets):
            skipped.append((p, "命中受保护域名"))
            continue
        added.append(p)
        if p not in st:
            st[p] = {"first": today}
        st[p]["last"] = today

    save_state(st)
    print("采样: %d 个候选 / 新增 %d / 跳过 %d"
          % (len(found), len(added), len(skipped)))
    for p, why in skipped:
        print("  跳过 %-28s %s" % (p, why))
    return 0


def cmd_build(args):
    st = load_state()
    today = datetime.date.today()
    kept, dropped = {}, []
    for p, meta in st.items():
        try:
            last = datetime.date.fromisoformat(meta.get("last", "1970-01-01"))
        except ValueError:
            dropped.append((p, "日期损坏"))
            continue
        if (today - last).days > KEEP_DAYS:
            dropped.append((p, "超过 %d 天未出现" % KEEP_DAYS))
        else:
            kept[p] = meta

    lines = []
    for p in sorted(kept, key=lambda x: (len(x), x)):
        lines.append("IP-CIDR6,%s,REJECT" % p)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    save_state(kept)

    print("构建: 保留 %d / 过期删除 %d → %s"
          % (len(kept), len(dropped), os.path.relpath(OUT, ROOT)))
    for p, why in dropped:
        print("  删除 %-28s %s" % (p, why))
    if not lines:
        print("  警告: 当前没有任何有效网段（下次 --sample 后恢复）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="在设备上采样（需国内网络）")
    ap.add_argument("--build", action="store_true", help="生成规则并清理过期（CI 用）")
    a = ap.parse_args()
    if a.sample == a.build:
        print("必须且只能指定 --sample 或 --build", file=sys.stderr)
        return 2
    return cmd_sample(a) if a.sample else cmd_build(a)


if __name__ == "__main__":
    sys.exit(main())
