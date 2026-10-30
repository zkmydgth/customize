#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分测试：jq CLI（oracle） vs tools/jq_runtime.js

对每条 jq 表达式，生成 N 个测试输入，分别求值并比对结果。
用法: python3 tools/test_equiv.py [--inputs 8] [--only 序号]
"""
import argparse
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jqparse import parse  # noqa


def collect_fields(node, out):
    if isinstance(node, dict):
        if node.get("t") == "field":
            out.add(node["n"])
        for v in node.values():
            collect_fields(v, out)
    elif isinstance(node, list):
        for x in node:
            collect_fields(x, out)


def rnd(depth, fields, rng):
    r = rng.random()
    if depth > 2 or r < 0.45:
        return rng.choice([None, True, False, 0, 1, 2.5, "", "str", "https://x/y", "av", "BANNER", [], {}])
    if r < 0.75:
        keys = rng.sample(sorted(fields), min(rng.randint(1, 4), len(fields))) if fields else ["k"]
        return {k: rnd(depth + 1, fields, rng) for k in keys}
    return [rnd(depth + 1, fields, rng) for _ in range(rng.randint(0, 3))]


def gen_inputs(fields, n, seed):
    rng = random.Random(seed)
    out = []
    # 形状化样本：所有字段各给一份
    shape = {}
    for f in sorted(fields):
        shape[f] = rng.choice([
            [{"a": 1}, {"a": 2}],
            {"a": 1, "key": "show", "value": 2, "type": "TIP"},
            "https://www.bilibili.com/blackboard/era/x",
            None,
        ])
    out.append(shape)
    for i in range(n - 1):
        d = {}
        for f in sorted(fields):
            d[f] = rnd(0, fields, rng)
        out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=int, default=8)
    ap.add_argument("--only", type=int, default=-1)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    data = json.load(open("/tmp/bodyrewrite.json", encoding="utf-8"))
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
        inputs = gen_inputs(fields, args.inputs, seed=idx * 977 + 13)
        cases.append({"id": idx, "ast": ast, "inputs": inputs})
        meta.append({"id": idx, "expr": expr, "pattern": item["pattern"]})

    open("/tmp/cases.json", "w", encoding="utf-8").write(json.dumps(cases, ensure_ascii=False))

    # JS 批量求值
    js = subprocess.run(["node", os.path.join(HERE, "test_runner.js"), "/tmp/cases.json"],
                        capture_output=True, text=True)
    if js.returncode != 0:
        print("node 失败:", js.stderr[:2000])
        sys.exit(1)
    js_res = {r["id"]: r for r in json.loads(js.stdout)}

    stats = {"same": 0, "bothfail": 0, "diff": 0}
    diffs = []
    for c in cases:
        cid = c["id"]
        expr = meta[[m["id"] for m in meta].index(cid)]["expr"]
        jsr = js_res[str(cid)] if str(cid) in js_res else js_res.get(cid, {})
        for k, inp in enumerate(c["inputs"]):
            p = subprocess.run(["jq", "-c", expr], input=json.dumps(inp, ensure_ascii=False),
                               capture_output=True, text=True)
            jq_ok = p.returncode == 0
            jq_vals = [json.loads(x) for x in p.stdout.strip().split("\n") if x.strip()] if jq_ok else []
            jsruns = jsr.get("runs", [])
            jr = jsruns[k] if k < len(jsruns) else {"ok": False}
            js_ok = jr.get("ok")
            if jq_ok and js_ok:
                if jq_vals == [json.loads(x) for x in jr["vals"]]:
                    stats["same"] += 1
                else:
                    stats["diff"] += 1
                    diffs.append({"id": cid, "expr": expr[:100], "in": inp,
                                  "jq": jq_vals, "js": [json.loads(x) for x in jr["vals"]]})
            elif (not jq_ok) and (not js_ok):
                stats["bothfail"] += 1
            else:
                stats["diff"] += 1
                diffs.append({"id": cid, "expr": expr[:100], "in": inp,
                              "jq_err": p.stderr.strip()[:120] if not jq_ok else None,
                              "jq": jq_vals if jq_ok else None,
                              "js": jr.get("vals") if js_ok else jr.get("err")})

    total = sum(stats.values())
    print(json.dumps({"total": total, **stats,
                      "pass_rate": round((stats["same"] + stats["bothfail"]) / max(total, 1), 4),
                      "parse_fail": parse_fail, "diff_samples": diffs[:6]},
                     ensure_ascii=False, indent=1))
    print("\n表达式总数: %d / 解析失败: %d" % (len(jq_items), len(parse_fail)))
    ok = (stats["diff"] == 0 and not parse_fail)
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
