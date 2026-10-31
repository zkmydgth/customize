#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游缺陷自愈器（纯函数，每个修复都计数，便于 report 与回归）。

设计原则：
  1. 只做「确定安全」的修复 —— 放宽而非收紧、规范化而非改语义
  2. 每个修复返回 (值, 是否改动, 原因)，绝不静默
  3. 修不了的不要猜，交给上层记为 unhandled 并在 CI 里暴露
"""
import re

SCHEME_RE = re.compile(r"http\??:\\/\\/")
INLINE_FLAG_RE = re.compile(r"^\(\?([imsx]+)\)")


def fix_scheme(text):
    """http:\\/\\/ 或 http?:\\/\\/  ->  https?:\\/\\/（只放宽）"""
    new = SCHEME_RE.sub(lambda m: "https?:\\/\\/", text)
    return new, new != text, "协议笔误 http->https?"


def strip_inline_flags(pattern):
    """把 JS 不支持的 (?i) 前缀拆成 flags。

    返回 (pattern, flags, changed)。仅处理开头的 (?i)(?m)(?s)(?x)。
    """
    m = INLINE_FLAG_RE.match(pattern)
    if not m:
        return pattern, "", False
    return pattern[m.end():], m.group(1).replace("x", ""), True


GITHUB_RAW_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/(?:raw|refs/heads)/(?:(main|master)/)?(.+?)(?=[,\s]|$)")


def fix_script_url(line):
    """github.com/<o>/<r>/raw/... 与 refs/heads/main/... 统一改成 raw 直链。

    前者会 302 跳转；SR 是否跟随重定向不确定，直链最稳。
    """
    def _sub(m):
        owner, repo, branch, rest = m.groups()
        return "https://raw.githubusercontent.com/%s/%s/%s/%s" % (
            owner, repo, branch or "main", rest)
    new = GITHUB_RAW_RE.sub(_sub, line)
    return new, new != line, "脚本地址改直链"


def fix_hostname(h):
    """MITM hostname 规范化：去 %APPEND%/%INSERT%、空白、大小写、重复点"""
    raw = h
    h = re.sub(r"^%(APPEND|INSERT)%\s*", "", h, flags=re.I).strip().lower()
    h = re.sub(r"\s+", "", h)
    h = re.sub(r"\.{2,}", ".", h).strip(".")
    return h, h != raw, "hostname 规范化"


def fix_misplaced_action(line):
    """上游把动作后缀写进了域名位置，导致规则永不命中。

    例：DOMAIN,tmead.y.qq.com-NO-DROP,REJECT
        -> DOMAIN,tmead.y.qq.com,REJECT-NO-DROP
    """
    m = re.match(r"^(DOMAIN(?:-SUFFIX|-KEYWORD)?),([^,\s]+?)-(NO-DROP|DROP),(REJECT)(.*)$", line)
    if not m:
        return line, False
    typ, host, act, _, rest = m.groups()
    return "%s,%s,REJECT-%s%s" % (typ, host, act, rest), True


def rule_key(line):
    """规则去重键：忽略注释与空白差异"""
    return re.sub(r"\s+", " ", line.strip())


def dedupe(lines):
    """完全重复的行去重（保序），返回 (新列表, 删除数)"""
    seen, out, removed = set(), [], 0
    for l in lines:
        k = rule_key(l)
        if k in seen:
            removed += 1
            continue
        seen.add(k)
        out.append(l)
    return out, removed


def pattern_compiles(p, flags=""):
    try:
        re.compile(p.replace("\\/", "/"), re.I if "i" in flags else 0)
        return True
    except re.error:
        return False


class FixStats:
    """修复计数，便于写进 report.json"""

    def __init__(self):
        self.counts = {}

    def add(self, reason, n=1):
        self.counts[reason] = self.counts.get(reason, 0) + n

    def as_dict(self):
        return self.counts


if __name__ == "__main__":
    for s in [r"^http:\/\/a.com", r"^http?:\/\/b.com", r"^https?:\/\/c.com"]:
        print(s, "->", fix_scheme(s)[0])
    for p in ["(?i)^https://x", "(?im)^https://y", "^https://z"]:
        print(p, "->", strip_inline_flags(p))
    for h in ["  %APPEND% Ad.Example.COM ", "a..b.com"]:
        print(repr(h), "->", fix_hostname(h)[0])


def _expand(s, limit=128):
    """展开 (a|b)? 形式，返回具体域名列表"""
    s = s.replace("(?:", "(")
    res = [s]
    while True:
        changed = False
        nxt = []
        for cur in res:
            m = re.search(r"\(([^()]*)\)(\?)?", cur)
            if not m:
                nxt.append(cur)
                continue
            changed = True
            opts = m.group(1).split("|")
            if m.group(2):
                opts.append("")
            for o in opts:
                nxt.append(cur[:m.start()] + o + cur[m.end():])
        res = nxt
        if not changed or len(res) > limit:
            break
    return [x for x in res if not re.search(r"[()?|]", x)]


def hosts_of_pattern(pat):
    m = re.search(r"https\??:?\\?/\\?/((?:[A-Za-z0-9_.()|?:\\-]|\\.)+)", pat)
    if not m:
        return []
    raw = m.group(1).replace("\\", "")
    raw = raw.split("/")[0].strip(".")
    if not raw:
        return []
    out = []
    for h in _expand(raw):
        h = h.strip(".")
        if re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z0-9-]+", h) or re.fullmatch(r"\d+\.\d+\.\d+\.\d+", h):
            out.append(h)
    return out
