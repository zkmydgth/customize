#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jq 子集解析器 -> AST(dict)，供 JS 运行时解释执行。"""

import json
import re


class JQError(Exception):
    pass


TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<num>-?\d+\.\d+(?:[eE][-+]?\d+)?|-?\d+(?:[eE][-+]?\d+)?)
  | (?P<str>"(?:\\.|[^"\\])*")
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<dotfield>\.[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>\|=|\+=|-=|\*=|/=|==|!=|<=|>=|//|\.\.|[.|,=<>+\-*/%?:;\[\](){}$])
""", re.X)


POS = []


def tokenize(src):
    POS.clear()
    toks, i, n = [], 0, len(src)
    while i < n:
        m = TOKEN_RE.match(src, i)
        if not m:
            raise JQError("token error at %d: %r" % (i, src[i:i + 20]))
        i = m.end()
        kind = m.lastgroup
        val = m.group()
        if kind == "ws":
            continue
        toks.append((kind, val))
        POS.append(m.start())
    toks.append(("eof", ""))
    return toks


def unescape(s):  # noqa: C901
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            n = s[i + 1]
            if n == "u":
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            if n == "n":
                out.append("\n")
            elif n == "t":
                out.append("\t")
            elif n == "r":
                out.append("\r")
            elif n == "b":
                out.append("\b")
            elif n == "f":
                out.append("\f")
            elif n == "/":
                out.append("/")
            elif n == '"':
                out.append('"')
            elif n == "\\":
                out.append("\\")
            else:
                out.append(n)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


class Parser:
    def __init__(self, src):
        self.t = tokenize(src)
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def at(self, val):
        return self.peek()[1] == val

    def eat(self, val):
        if self.at(val):
            self.i += 1
            return True
        return False

    def expect(self, val):
        if not self.eat(val):
            raise JQError("expect %r, got %r" % (val, self.peek()))

    # ---- 语法层级 ----
    def parse(self):
        e = self.expr()
        if self.peek()[0] != "eof":
            raise JQError("trailing token %r" % (self.peek(),))
        return e

    def expr(self):
        return self.pipe()

    def pipe(self):
        left = self.assign()
        while self.at("|"):
            self.next()
            left = {"t": "pipe", "l": left, "r": self.assign()}
        return left

    def assign(self):
        left = self.comma()
        k, v = self.peek()
        if v in ("=", "|=", "+=", "-=", "*=", "/="):
            self.next()
            return {"t": "assign", "op": v, "l": left, "r": self.assign()}
        return left

    def comma(self):
        left = self.alt()
        while self.at(","):
            self.next()
            left = {"t": "comma", "l": left, "r": self.alt()}
        return left

    # 对象成员值：裸逗号属于成员分隔符，不能吃进表达式
    def assign_nc(self):
        left = self.alt()
        k, v = self.peek()
        if v in ("=", "|=", "+=", "-=", "*=", "/="):
            self.next()
            return {"t": "assign", "op": v, "l": left, "r": self.assign_nc()}
        return left

    def pipe_nc(self):
        left = self.assign_nc()
        while self.at("|"):
            self.next()
            left = {"t": "pipe", "l": left, "r": self.assign_nc()}
        return left

    def alt(self):
        left = self.orop()
        while self.at("//"):
            self.next()
            right = self.orop()
            left = {"t": "alt", "l": left, "r": right}
        return left

    def orop(self):
        left = self.andop()
        while self.at("or"):
            self.next()
            left = {"t": "bin", "op": "or", "l": left, "r": self.andop()}
        return left

    def andop(self):
        left = self.cmp()
        while self.at("and"):
            self.next()
            left = {"t": "bin", "op": "and", "l": left, "r": self.cmp()}
        return left

    def cmp(self):
        left = self.add()
        k, v = self.peek()
        if v in ("==", "!=", "<", ">", "<=", ">="):
            self.next()
            return {"t": "bin", "op": v, "l": left, "r": self.add()}
        return left

    def add(self):
        left = self.mul()
        while self.peek()[1] in ("+", "-") and self.peek()[0] == "op":
            op = self.next()[1]
            left = {"t": "bin", "op": op, "l": left, "r": self.mul()}
        return left

    def mul(self):
        left = self.unary()
        while self.peek()[1] in ("*", "/", "%") and self.peek()[0] == "op":
            op = self.next()[1]
            left = {"t": "bin", "op": op, "l": left, "r": self.unary()}
        return left

    def unary(self):
        if self.at("-"):
            self.next()
            return {"t": "un", "op": "-", "e": self.unary()}
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            if self.peek()[0] == "dotfield":
                tok = self.next()[1]
                e = {"t": "pipe", "l": e, "r": {"t": "field", "n": tok[1:]}}
                continue
            if self.at("["):
                self.next()
                if self.eat("]"):
                    e = {"t": "pipe", "l": e, "r": {"t": "iter"}}
                else:
                    idx = self.expr()
                    self.expect("]")
                    e = {"t": "pipe", "l": e, "r": {"t": "index", "e": idx}}
                continue
            if self.at("?"):
                self.next()
                if e.get("t") == "pipe":
                    e = {"t": "pipe", "l": e["l"], "r": {"t": "opt", "e": e["r"]}}
                else:
                    e = {"t": "opt", "e": e}
                continue
            break
        return e

    def primary(self):  # noqa: C901
        k, v = self.peek()
        if k == "dotfield":
            self.next()
            return {"t": "field", "n": v[1:]}
        if v == "(":
            self.next()
            e = self.expr()
            self.expect(")")
            return e
        if v == ".":
            self.next()
            k2, v2 = self.peek()
            if k2 == "str":
                self.next()
                return {"t": "field", "n": unescape(v2[1:-1])}
            return {"t": "id"}
        if v == "..":
            self.next()
            return {"t": "call", "f": "recurse", "args": []}
        if v == "[":
            self.next()
            if self.eat("]"):
                return {"t": "arr", "e": None}
            e = self.expr()
            self.expect("]")
            return {"t": "arr", "e": e}
        if v == "{":
            self.next()
            pairs = []
            if not self.at("}"):
                while True:
                    if self.at("("):
                        self.next()
                        kexp = self.expr()
                        self.expect(")")
                    else:
                        kk, kv = self.next()
                        if kk == "ident":
                            kexp = {"t": "lit", "v": kv}
                        elif kk == "str":
                            kexp = {"t": "lit", "v": unescape(kv[1:-1])}
                        else:
                            raise JQError("bad object key %r" % kv)
                    if self.eat(":"):
                        vexp = self.pipe_nc()
                    else:
                        vexp = {"t": "field", "n": kexp["v"]}
                    pairs.append([kexp, vexp])
                    if not self.eat(","):
                        break
                    if self.at("}"):   # 容忍上游的尾逗号（jq 原生会报错）
                        break
            self.expect("}")
            return {"t": "obj", "pairs": pairs}
        if v == "if":
            self.next()
            cond = self.expr()
            self.expect("then")
            then = self.expr()
            els = None
            if self.at("elif"):
                self.next()
                els = self.if_chain()
            elif self.at("else"):
                self.next()
                els = self.expr()
                self.expect("end")
            else:
                self.expect("end")
            return {"t": "if", "c": cond, "a": then, "b": els}
        if v == "try":
            self.next()
            e = self.expr()
            c = None
            if self.at("catch"):
                self.next()
                c = self.expr()
            return {"t": "try", "e": e, "c": c}
        if k == "num":
            self.next()
            return {"t": "lit", "v": json.loads(v)}
        if k == "str":
            self.next()
            return {"t": "lit", "v": unescape(v[1:-1])}
        if k == "ident":
            self.next()
            if v == "true":
                return {"t": "lit", "v": True}
            if v == "false":
                return {"t": "lit", "v": False}
            if v == "null":
                return {"t": "lit", "v": None}
            if self.at("("):
                self.next()
                args = []
                if not self.at(")"):
                    while True:
                        args.append(self.expr())
                        if not self.eat(";"):
                            break
                self.expect(")")
                return {"t": "call", "f": v, "args": args}
            return {"t": "call", "f": v, "args": []}
        raise JQError("unexpected token %r" % (self.peek(),))

    def if_chain(self):
        self.expect("elif")
        cond = self.expr()
        self.expect("then")
        then = self.expr()
        els = None
        if self.at("elif"):
            els = self.if_chain()
        elif self.at("else"):
            self.next()
            els = self.expr()
            self.expect("end")
        else:
            self.expect("end")
        return {"t": "if", "c": cond, "a": then, "b": els}


def parse(src):
    p = Parser(src)
    try:
        return p.parse()
    except JQError as e:
        pos = POS[min(p.i, len(POS) - 1)] if POS else 0
        raise JQError("%s | near=%s | src=%r" % (e, src[pos:pos + 120], pos)) from None


if __name__ == "__main__":
    import sys
    print(json.dumps(parse(sys.argv[1]), ensure_ascii=False))
