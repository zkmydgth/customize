#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跟踪知乎的 IPv6 网段，自动生成 IP-CIDR6 屏蔽规则（纯 CI 可跑）。

背景：知乎 App 拿到 AAAA 后会直连 IPv6，Shadowrocket 只看到 IP、
无法按域名解密，Map Local 与 Script 全部失效，所以要在 IP 层拦。

关键技巧：GitHub Actions 在海外，直接查 DNS 拿到的是海外 CDN 段
（如 240d:c010::/32），与中国移动网络完全不同。因此用 **EDNS Client Subnet**
把"查询来源"伪装成中国各地运营商，才能拿到国内真实使用的段。

用法：
  python3 tools/track_ipv6.py --sample    # 采样（带 ECS，CI 可跑）
  python3 tools/track_ipv6.py --build     # 过期清理 + 生成规则
  python3 tools/track_ipv6.py --sample --build   # 两步都做

输出：tools/ipv6-auto.txt（由 convert.py 并入产物）
"""
import argparse
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(HERE, "ipv6-state.json")
OUT = os.path.join(HERE, "ipv6-auto.txt")

DOH = "https://dns.alidns.com/resolve"

# 需要屏蔽的 App（知乎）
TARGETS = [
    "api.zhihu.com", "appcloud2.zhihu.com", "www.zhihu.com",
    "m-cloud.zhihu.com", "picx.zhimg.com", "duga.zhihu.com",
    "zhuanlan.zhihu.com", "page-info.zhihu.com",
]

# 不能误伤的关键域名（微信文件传输、支付、云盘等）
PROTECT = [
    "filehelper.weixin.qq.com", "szfilehelper.weixin.qq.com",
    "dldir1.qq.com", "vweixinf.tc.qq.com", "short.weixin.qq.com",
    "wx.qq.com", "mp.weixin.qq.com",
]

# 用 ECS 伪装成不同地区的三大运营商，覆盖知乎可能调度的所有节点
ECS = [
    "117.136.0.0/16", "223.104.0.0/16", "120.230.0.0/16",   # 移动
    "222.90.0.0/16", "183.14.0.0/16", "61.183.0.0/16",      # 电信
    "113.24.0.0/16", "119.167.0.0/16", "123.125.0.0/16",    # 联通
]

PREFIX = 48        # 宁杀错不放过：/48 覆盖整个 CDN 分配单元，
                   # 误伤的其他 App 会自动回退 IPv4，不影响可用性
KEEP_DAYS = 7      # 多少天没再出现就删除


def query(name, ecs):
    """带 ECS 查询 AAAA"""
    q = urllib.parse.urlencode({"name": name, "type": "AAAA",
                                "edns_client_subnet": ecs})
    req = urllib.request.Request(DOH + "?" + q,
                                 headers={"User-Agent": "sr-adblock-track"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    return [x["data"] for x in d.get("Answer", []) if x.get("type") == 28]


def to_prefix(addr, bits=PREFIX):
    g = (addr.split(":") + ["0"] * 8)[:8]
    keep = bits // 16
    shown = g[:keep]
    while shown and shown[-1] in ("0", "0000"):
        shown.pop()
    body = ":".join(shown)
    return (body + "::/%d" % bits) if body else "::/%d" % bits


def gkey(prefix):
    """按 PREFIX 位数取比较键"""
    body = prefix.split("/")[0].rstrip(":")
    n = PREFIX // 16
    return ":".join((body.split(":") + ["0"] * n)[:n])


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1, sort_keys=True)


def cmd_sample():  # noqa: C901
    today = datetime.date.today().isoformat()

    # 先建立受保护域名占用的 /48 集合
    protected = set()
    for d in PROTECT:
        for ecs in ECS[:3]:
            try:
                for a in query(d, ecs):
                    protected.add(gkey(to_prefix(a)))
            except Exception:  # noqa: BLE001, S110
                continue

    found = set()
    for d in TARGETS:
        for ecs in ECS:
            try:
                for a in query(d, ecs):
                    found.add(to_prefix(a))
            except Exception:  # noqa: BLE001, S110
                continue

    st = load_state()
    added, skipped = [], []
    for p in sorted(found):
        if gkey(p) in protected:
            skipped.append((p, "与受保护域名同段"))
            continue
        if p not in st:
            st[p] = {"first": today}
            added.append(p)
        st[p]["last"] = today
    save_state(st)

    print("采样: %d 个候选 / 新增 %d / 跳过 %d（受保护 %d 段）"
          % (len(found), len(added), len(skipped), len(protected)))
    for p in added:
        print("  + %s" % p)
    for p, why in skipped:
        print("  - %s  %s" % (p, why))
    return 0


def cmd_build():
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

    lines = ["IP-CIDR6,%s,REJECT" % p for p in sorted(kept)]
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    save_state(kept)

    print("构建: 保留 %d / 过期 %d → %s"
          % (len(kept), len(dropped), os.path.relpath(OUT, ROOT)))
    for p, why in dropped:
        print("  - %s  %s" % (p, why))
    if not lines:
        print("  警告: 无有效网段（首次运行请先 --sample）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="ECS 采样（CI 可跑）")
    ap.add_argument("--build", action="store_true", help="清理过期并生成规则")
    a = ap.parse_args()
    if not (a.sample or a.build):
        print("需指定 --sample 和/或 --build", file=sys.stderr)
        return 2
    rc = 0
    if a.sample:
        rc = cmd_sample()
    if a.build and rc == 0:
        rc = cmd_build()
    return rc


if __name__ == "__main__":
    sys.exit(main())
