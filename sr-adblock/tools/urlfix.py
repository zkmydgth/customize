#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游 URL 正则的协议笔误修正（转换期统一处理，保证每次同步都生效）。

上游存在两类笔误：
  1. 只写 http:\\/\\/   —— 实际服务已是 https，规则永不触发
  2. 写成 http?:\\/\\/   —— "htt" + 可选 p，明显笔误

两者统一放宽为 https?:\\/\\/（同时匹配 http 与 https），
只放宽、不收紧，不会让原本能匹配的 URL 失效。
"""
import re

SCHEME_RE = re.compile(r"http\??:\\/\\/")


def fix_scheme(text):
    """把 http:\\/\\/ / http?:\\/\\/ 放宽成 https?:\\/\\/；已经是 https? 的不动。"""
    return SCHEME_RE.sub(lambda m: "https?:\\/\\/", text)


def count_fixed(lines):
    return sum(1 for l in lines if SCHEME_RE.search(l))


if __name__ == "__main__":
    samples = [
        r"^http:\/\/a.com\/x",
        r"http:\/\/b.com",
        r"^http?:\/\/c.com",
        r"^https?:\/\/d.com",
        r"^https:\/\/e.com",
    ]
    for s in samples:
        print(f"{s:28s} -> {fix_scheme(s)}")
