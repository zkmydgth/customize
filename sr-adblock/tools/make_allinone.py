#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 all-in-one 模块（去广告 + 解锁合并）。

为什么必须合并：Shadowrocket 同时安装多个模块时，**只加载其中一个的 MITM**，
另一个模块的 Map Local / Script 会全部静默失效（2026-11-07 实测）。

用法:
  python3 tools/make_allinone.py \
    --ad dist/blockAds.sr.module \
    --unlock dist/unlock.srmodule \
    --out dist/all-in-one.srmodule \
    --raw-url https://raw.githubusercontent.com/.../dist/all-in-one.srmodule
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--ad", default="dist/blockAds.sr.module")
    ap.add_argument("--unlock", default="dist/unlock.srmodule")
    ap.add_argument("--out", default="dist/all-in-one.srmodule")
    ap.add_argument("--raw-url", default="")
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    for p in (a.ad, a.unlock):
        if not os.path.exists(p):
            print("ERROR: 缺少输入 %s" % p, file=sys.stderr)
            return 1

    with tempfile.NamedTemporaryFile(suffix=".srmodule", delete=False) as f:
        tmp = f.name
    with open(a.ad, "rb") as src, open(tmp, "wb") as dst:
        dst.write(src.read())

    r = subprocess.run([sys.executable, os.path.join(HERE, "merge_module.py"),
                        "--main", tmp, "--add", a.unlock], capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR: merge_module 失败\n" + r.stderr[-500:], file=sys.stderr)
        os.unlink(tmp)
        return 1

    with open(tmp, encoding="utf-8") as fh:
        text = fh.read()
    os.unlink(tmp)

    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    text = re.sub(r"^#!name=.*$", "#!name=SR 全家桶（去广告+解锁）", text, count=1, flags=re.M)
    # desc / tag 要与"含解锁"一致，date 用构建日期（上游日期在头部另有说明）
    text = re.sub(r"^#!desc=.*$",
                  "#!desc=由两个上游自动合并：fmz200 去广告（含 deezertidal 去广告部分）+ deezertidal App 解锁。"
                  "Shadowrocket 同时装多个模块时只加载其中一个的 MITM，因此必须只装这一个。",
                  text, count=1, flags=re.M)
    text = re.sub(r"^#!tag=.*$", "#!tag=去广告,解锁", text, count=1, flags=re.M)
    text = re.sub(r"^#!date=.*$", "#!date=" + today, text, count=1, flags=re.M)
    if a.raw_url:
        if re.search(r"^#!raw-url=", text, flags=re.M):
            text = re.sub(r"^#!raw-url=.*$", "#!raw-url=" + a.raw_url, text, count=1, flags=re.M)
        else:
            text = text.replace("\n\n", "\n#!raw-url=" + a.raw_url + "\n\n", 1)
    # 只保留一个 MITM 行（合并可能产生重复）
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.rstrip() + "\n")

    # 统计
    secs, cur = {}, None
    for l in text.split("\n"):
        m = re.match(r"^\[([^\]]+)\]", l.strip())
        if m:
            cur = m.group(1)
            secs.setdefault(cur, 0)
            continue
        if cur and l.strip() and not l.strip().startswith("#"):
            secs[cur] += 1
    mitm = 0
    for l in text.split("\n"):
        s = l.strip()
        if s.lower().startswith("hostname") and "=" in s:
            v = re.sub(r"^%(APPEND|INSERT)%\s*", "", s.split("=", 1)[1], flags=re.I)
            mitm = len([h for h in v.split(",") if h.strip()])

    print("all-in-one: Rule=%d URLRewrite=%d Script=%d MITM=%d bytes=%d"
          % (secs.get("Rule", 0), secs.get("URL Rewrite", 0), secs.get("Script", 0),
             mitm, os.path.getsize(a.out)))
    if a.report:
        import json
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump({"rule": secs.get("Rule", 0), "url_rewrite": secs.get("URL Rewrite", 0),
                       "script": secs.get("Script", 0), "mitm": mitm,
                       "bytes": os.path.getsize(a.out)}, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
