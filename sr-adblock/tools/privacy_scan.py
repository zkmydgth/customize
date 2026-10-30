#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""隐私扫描（安全版）：脚本本身不含任何真实标识。

设计约束（重要）：
  1. 只使用通用正则，不写死任何真实手机号 / 邮箱 / 用户名 / IP
  2. 命中时只输出「文件:行号 [规则名]」，**绝不输出匹配内容**
     —— public 仓库的 Actions 日志对所有人可见，打印内容等于公开泄露
  3. 真实标识比对走可选的 --state-file（本地文件，不入库、不进 CI）

用法:
  python3 tools/privacy_scan.py                 # 扫默认范围
  python3 tools/privacy_scan.py --all           # 含生成物
  python3 tools/privacy_scan.py --state-file /var/minis/memory/.secrets/real_ids.txt
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 高危：出现在任何位置都必须报（含生成物）
HIGH = [
    ("github-token", re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("private-key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("local-path", re.compile(r"/var/minis|/Users/[A-Za-z]|C:\\Users\\")),
    ("bearer", re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}")),
]

# 一般：只扫源码（生成物里的 IP/域名来自公开上游，属于误报源）
NORMAL = [
    ("cn-mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("private-ip", re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
                              r"\b192\.168\.\d{1,3}\.\d{1,3}\b|"
                              r"\b172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}\b")),
]

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".cache",
             ".ruff_cache", ".pytest_cache", ".mypy_cache"}
GEN_DIRS = {"dist", "build", "scripts"}   # 生成物
EMAIL_ALLOW = {"github-actions[bot]@users.noreply.github.com",
               "zkmydgth@users.noreply.github.com", "users.noreply.github.com"}
SKIP_FILES = {"tools/privacy_scan.py"}   # 扫描器自身定义了这些模式
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".woff", ".woff2"}


def walk(root, include_gen):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and (include_gen or d not in GEN_DIRS)]
        for f in files:
            if os.path.splitext(f)[1].lower() in SKIP_EXT:
                continue
            full = os.path.join(base, f)
            if os.path.relpath(full, root).replace(os.sep, "/") in SKIP_FILES:
                continue
            yield full


def scan(path, rules):
    hits = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for no, line in enumerate(fh, 1):
                if len(line) > 4000:      # 超长行（生成的 JS 表）只看前 4000 字符
                    line = line[:4000]
                for name, rx in rules:
                    if rx.search(line):
                        if name == "email" and any(a in line for a in EMAIL_ALLOW):
                            continue
                        hits.append((no, name))
    except OSError:
        pass
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--all", action="store_true", help="同时扫描生成物目录")
    ap.add_argument("--state-file", default="", help="本地真实标识文件（不入库）")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    extra = []
    if a.state_file and os.path.exists(a.state_file):
        with open(a.state_file, encoding="utf-8") as fh:
            vals = [l.strip() for l in fh if l.strip() and not l.startswith("#")]
        for i, v in enumerate(vals):
            extra.append(("real-id#%d" % (i + 1), re.compile(re.escape(v))))
        if not a.quiet:
            print("已加载真实标识 %d 条（仅本地比对，不打印内容）" % len(vals))

    total = 0
    files = list(walk(a.root, a.all))
    for path in files:
        rel = os.path.relpath(path, a.root)
        rules = HIGH + (NORMAL if not rel.startswith(tuple(GEN_DIRS)) else []) + extra
        hits = scan(path, rules)
        for no, name in hits:
            # 只输出位置与规则名，绝不输出匹配内容
            print("%s:%d [%s]" % (rel, no, name))
        total += len(hits)

    print("\n扫描 %d 个文件，命中 %d 处" % (len(files), total))
    if total:
        print("RESULT: FAIL（请人工确认，勿在日志中展开内容）")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
