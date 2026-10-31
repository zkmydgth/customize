#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分测试：jq CLI（oracle） vs tools/jq_runtime.js

对每条 jq 表达式生成多组输入，分别求值并比对结果。

2026-10-31 审计修复覆盖空洞：
  - 旧实现只按 AST 里的 field 节点合成输入，`delpaths([["adsplash"]])` 这类
    「路径写在字符串字面量里」的表达式拿到的输入与规则无关（40/72 条），
    导致 44/72 条规则在整个测试中输出从未改变 —— 等于没测。
  - 现在从 delpaths/getpath/setpath/del/赋值左侧/if 条件反推**真实路径链**，
    构造嵌套对象，并强制每条规则至少「改变过一次输出」，否则算未覆盖。

用法: python3 tools/test_equiv.py [--inputs 8] [--only N] [--strict-coverage]
"""
import argparse
import copy
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jqparse import parse  # noqa


# ---------- 旧：字段集合（保留给随机样本） ----------
def collect_fields(node, out):
    if isinstance(node, dict):
        if node.get("t") == "field":
            out.add(node["n"])
        for v in node.values():
            collect_fields(v, out)
    elif isinstance(node, list):
        for x in node:
            collect_fields(x, out)


# ---------- 新：从 AST 反推真实路径 ----------
def lit_seq(n):
    """把 [a,b] / (a,b) / comma 链展开成路径元素列表（数字保留为 int，用作数组下标）"""
    if not isinstance(n, dict):
        return []
    t = n.get("t")
    if t == "lit":
        v = n.get("v")
        if isinstance(v, bool):
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            return [v]
        return []
    if t == "comma":
        return lit_seq(n["l"]) + lit_seq(n["r"])
    if t == "arr":
        return lit_seq(n["e"])
    if t == "pipe":
        return lit_seq(n["l"]) + lit_seq(n["r"])
    return []


def path_list(n):
    """把 delpaths 的参数展开成多条路径：[[ "a","b" ],["c"]]"""
    if not isinstance(n, dict):
        return []
    t = n.get("t")
    if t == "comma":
        return path_list(n["l"]) + path_list(n["r"])
    if t == "arr":
        inner = n.get("e")
        if isinstance(inner, dict) and inner.get("t") == "comma":
            l, r = inner["l"], inner["r"]
            if isinstance(l, dict) and l.get("t") == "arr":
                return path_list(l) + path_list(r)
        p = lit_seq(inner)
        return [p] if p else []
    p = lit_seq(n)
    return [p] if p else []


def expr_paths(n, depth=0):  # noqa: C901
    """返回该表达式可能指向的路径（列表的列表）"""
    if not isinstance(n, dict) or depth > 8:
        return []
    t = n.get("t")
    if t == "field":
        return [[n["n"]]]
    if t == "pipe":
        l, r = expr_paths(n["l"], depth + 1), expr_paths(n["r"], depth + 1)
        if l and r:
            return [a + b for a in l for b in r][:16]
        return l or r
    if t == "assign":
        return expr_paths(n.get("l"), depth + 1)
    if t == "if":
        return (expr_paths(n.get("c"), depth + 1)
                + expr_paths(n.get("a"), depth + 1)
                + expr_paths(n.get("b"), depth + 1))
    if t == "call":
        f = n.get("f")
        # getpath/setpath/delpaths 的参数是「路径字面量」，直接取
        if f in ("getpath", "setpath", "delpaths"):
            args = n.get("args", [])
            return path_list(args[0]) if args else []
        if f in ("del", "has"):
            out = []
            for a in n.get("args", []):
                out += expr_paths(a, depth + 1)
            return out
    return []


def collect_root_paths(ast):  # noqa: C901
    """遍历 AST，收集所有「根位置」路径"""
    found = []

    def walk(node, depth=0):
        if isinstance(node, list):
            for x in node:
                walk(x, depth + 1)
            return
        if not isinstance(node, dict) or depth > 12:
            return
        t = node.get("t")
        if (t in ("assign", "if")
                or (t == "call" and node.get("f") in ("del", "delpaths", "getpath", "setpath"))):
            found.extend(expr_paths(node, 0))
        for v in node.values():
            walk(v, depth + 1)

    walk(ast)
    seen, out = set(), []
    for p in found:
        if not p:
            continue
        k = tuple(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def set_path(container, path, leaf):
    """按路径写入；数字下标会构造数组"""
    if not path:
        return
    k = path[0]
    last = len(path) == 1
    if isinstance(k, int):
        if not isinstance(container, list):
            return
        while len(container) <= k:
            container.append(None)
        if last:
            container[k] = copy.deepcopy(leaf)
            return
        want_list = isinstance(path[1], int)
        if not isinstance(container[k], list if want_list else dict):
            container[k] = [] if want_list else {}
        set_path(container[k], path[1:], leaf)
    else:
        if not isinstance(container, dict):
            return
        if last:
            container[k] = copy.deepcopy(leaf)
            return
        want_list = isinstance(path[1], int)
        if not isinstance(container.get(k), list if want_list else dict):
            container[k] = [] if want_list else {}
        set_path(container[k], path[1:], leaf)


def build_nested(paths, leaf):
    """按路径列表构造嵌套对象/数组"""
    root = {}
    for p in paths:
        if p and isinstance(p[0], int):
            continue
        set_path(root, p, leaf)
    return root


def rnd(depth, fields, rng):
    r = rng.random()
    if depth > 2 or r < 0.45:
        return rng.choice([None, True, False, 0, 1, 2.5, "", "str", "https://x/y", "av", "BANNER", [], {}])
    if r < 0.75:
        keys = rng.sample(sorted(fields), min(rng.randint(1, 4), len(fields))) if fields else ["k"]
        return {k: rnd(depth + 1, fields, rng) for k in keys}
    return [rnd(depth + 1, fields, rng) for _ in range(rng.randint(0, 3))]


def collect_constraints(node, out, depth=0):
    """收集 .field OP literal 形式的比较条件，用来造能触发分支的样本"""
    if isinstance(node, list):
        for x in node:
            collect_constraints(x, out, depth + 1)
        return
    if not isinstance(node, dict) or depth > 12:
        return
    if node.get("t") == "bin" and node.get("op") in ("==", "!=", "<", ">", "<=", ">=", "and", "or"):
        l, r = node.get("l"), node.get("r")
        if isinstance(l, dict) and l.get("t") == "field" and isinstance(r, dict) and r.get("t") == "lit":
            out.append((l["n"], r.get("v")))
        elif isinstance(r, dict) and r.get("t") == "field" and isinstance(l, dict) and l.get("t") == "lit":
            out.append((r["n"], l.get("v")))
    for v in node.values():
        collect_constraints(v, out, depth + 1)


def constrained_leaves(constraints):
    """按条件造「命中 / 不命中」两种叶子"""
    f = {}
    for k, v in constraints:
        if isinstance(k, str) and isinstance(v, (str, int)) and not isinstance(v, bool):
            f[k] = v
    out = []
    if f:
        out.append([dict(f), {"a": 1}])
        out.append([{k: "__other__" for k in f}, {"a": 1}])
        out.append(dict(f))
    return out


LEAVES = [
    # 万能元素：把常见字段一次给全，让 `select(.title | test(...))` 这类
    # 「字段缺失即报错」的规则也能成功执行（否则全程 bothfail，等于没测）
    [{"title": "直播", "type": "ad", "id": "1", "ad": 1, "ad_info": None,
      "bizType": "x", "card_goto": "vertical_ad_a", "key": "show",
      "item": {"list": [{"bizType": "x"}]},
      "itemList": [{"title": "直播"}],
      "module_data": {"items": [{"a": 1}]}}],
    [{"a": 1}, {"a": 2}],                                        # 普通数组
    [{"ad": 1}, {"a": 2}],                                       # select(.ad | not)
    [{"ad_info": None, "card_goto": "vertical_ad_a"}, {"a": 1}],  # 条件命中
    [{"type": "BANNER", "module_data": {"items": [{"a": 1}]}}],   # 嵌套卡片
    [{"item": {"list": [{"bizType": "x"}]}}],                    # 深层数组
    [{"item": {"list": [{"bizType": "SceneListenCard"}]}}],      # 深层数组（命中过滤）
    [{"itemList": [{"title": "直播"}]}],                          # 深层标题
    {"a": 1, "type": "ad", "key": "show"},                       # 对象
    {"data": {"items": [1], "show": [1]}},                       # B站 splash
    True,
    "https://www.bilibili.com/blackboard/x",
    0,
]


def gen_inputs(fields, paths, constraints, n, seed):
    rng = random.Random(seed)
    out, seen = [], set()

    def add(o):
        k = json.dumps(o, sort_keys=True)
        if k not in seen:
            seen.add(k)
            out.append(o)

    # 1) 按真实路径构造：先按表达式里的比较条件造叶子，再补通用形态
    leaves = constrained_leaves(constraints) + LEAVES
    if paths:
        for leaf in leaves:
            add(build_nested(paths, leaf))
        # 逐条路径单独实例化（避免互相覆盖导致某条路径消失）
        for p in paths:
            add(build_nested([p], [{"a": 1}, {"a": 2}]))

    # 2) 全字段形状样本
    shape = {}
    for f in sorted(fields):
        shape[f] = rng.choice([
            [{"a": 1}, {"a": 2}],
            {"a": 1, "key": "show", "value": 2, "type": "TIP"},
            "https://www.bilibili.com/blackboard/era/x",
            None,
        ])
    add(shape)

    # 3) 随机兜底
    for _ in range(max(n - len(out), 2)):
        d = {}
        for f in sorted(fields):
            d[f] = rnd(0, fields, rng)
        add(d)
    return out


def main():  # noqa: C901
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=int, default=8)
    ap.add_argument("--only", type=int, default=-1)
    ap.add_argument("--strict-coverage", action="store_true",
                    help="有规则全程未改变输出即判失败")
    args = ap.parse_args()

    with open("/tmp/bodyrewrite.json", encoding="utf-8") as f:
        data = json.load(f)
    jq_items = [x for x in data if x.get("type") == "jq"]
    if args.only >= 0:
        jq_items = [jq_items[args.only]]

    cases, meta = [], []
    parse_fail = []
    for idx, item in enumerate(jq_items):
        expr = item["expr"]
        try:
            ast = parse(expr)
        except Exception as e:
            parse_fail.append({"idx": idx, "expr": expr[:120], "err": str(e)})
            continue
        fields = set()
        collect_fields(ast, fields)
        paths = collect_root_paths(ast)
        cons = []
        collect_constraints(ast, cons)
        inputs = gen_inputs(fields, paths, cons, args.inputs, seed=idx * 977 + 13)
        cases.append({"id": idx, "ast": ast, "inputs": inputs})
        meta.append({"id": idx, "expr": expr, "pattern": item["pattern"], "paths": paths})

    with open("/tmp/cases.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(cases, ensure_ascii=False))

    js = subprocess.run(["node", os.path.join(HERE, "test_runner.js"), "/tmp/cases.json"],
                        capture_output=True, text=True)
    if js.returncode != 0:
        print("node 失败:", js.stderr[:2000])
        sys.exit(1)
    js_res = {r["id"]: r for r in json.loads(js.stdout)}

    stats = {"same": 0, "bothfail": 0, "diff": 0}
    diffs = []
    uncovered = []
    meta_by_id = {m["id"]: m for m in meta}

    for c in cases:
        cid = c["id"]
        m = meta_by_id[cid]
        jsr = js_res[str(cid)] if str(cid) in js_res else js_res.get(cid, {})
        changed = False
        ok_seen = False
        for k, inp in enumerate(c["inputs"]):
            p = subprocess.run(["jq", "-c", m["expr"]],
                               input=json.dumps(inp, ensure_ascii=False),
                               capture_output=True, text=True)
            jq_ok = p.returncode == 0
            jq_vals = ([json.loads(x) for x in p.stdout.strip().split("\n") if x.strip()]
                       if jq_ok else [])
            jsruns = jsr.get("runs", [])
            jr = jsruns[k] if k < len(jsruns) else {"ok": False}
            js_ok = jr.get("ok")
            if jq_ok and js_vals_equal(jq_vals, jr.get("vals", []), js_ok):
                stats["same"] += 1
                ok_seen = True
                if jq_vals != [inp]:
                    changed = True
            elif (not jq_ok) and (not js_ok):
                stats["bothfail"] += 1
            else:
                stats["diff"] += 1
                diffs.append({"id": cid, "expr": m["expr"][:100], "in": inp,
                              "jq_err": p.stderr.strip()[:120] if not jq_ok else None,
                              "jq": jq_vals if jq_ok else None,
                              "js": jr.get("vals") if js_ok else jr.get("err")})
        if not changed:
            uncovered.append({"id": cid, "expr": m["expr"][:100],
                              "paths": m["paths"][:4], "ok_compared": ok_seen})

    total = sum(stats.values())
    print(json.dumps({"total": total, **stats,
                      "pass_rate": round(stats["same"] / max(total, 1), 4),
                      "covered": len(cases) - len(uncovered),
                      "uncovered": len(uncovered),
                      "parse_fail": parse_fail,
                      "diff_samples": diffs[:6]},
                     ensure_ascii=False, indent=1))
    if uncovered:
        print("\n未覆盖（输出从未改变，等于没测）：")
        for u in uncovered[:12]:
            print("  #%d 路径=%s  %s" % (u["id"], u["paths"], u["expr"]))
        if len(uncovered) > 12:
            print("  ... 共 %d 条" % len(uncovered))

    print("\n表达式总数: %d / 解析失败: %d / 已覆盖: %d" %
          (len(jq_items), len(parse_fail), len(cases) - len(uncovered)))
    ok = (stats["diff"] == 0 and not parse_fail)
    if args.strict_coverage and uncovered:
        ok = False
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


def js_vals_equal(jq_vals, js_vals_str, js_ok):
    if not js_ok:
        return False
    try:
        return jq_vals == [json.loads(x) for x in js_vals_str]
    except Exception:
        return False


if __name__ == "__main__":
    main()
