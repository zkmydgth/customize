#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把上游 [Body Rewrite] 的 96 条（72 jq + 24 字符串替换）编译成 1 个 SR 脚本。

输出:
  scripts/body-rewrite.js     运行时 + 规则表
  build/body-rewrite.rules    96 行 [Script] 配置
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from jqparse import parse

SRC = "/tmp/bodyrewrite.json"
RT = os.path.join(HERE, "jq_runtime.js")


def split_last2(s):
    """从右往左取最后两个参数（引号字符串或非空白串）"""
    s = s.rstrip()
    parts, i = [], len(s)
    while i > 0 and len(parts) < 2:
        while i > 0 and s[i - 1].isspace():
            i -= 1
        if i == 0:
            break
        if s[i - 1] == '"':
            j = i - 2
            while j >= 0:
                if s[j] == '"' and (j == 0 or s[j - 1] != "\\"):
                    break
                j -= 1
            parts.insert(0, s[j:i])
            i = j
        else:
            j = i
            while j > 0 and not s[j - 1].isspace():
                j -= 1
            parts.insert(0, s[j:i])
            i = j
    return parts


def parse_replace(raw):
    m = re.match(r"^http-response\s+(\S+)\s+(.*)$", raw)
    if not m:
        return None
    pat, rest = m.group(1), m.group(2).strip()
    toks = split_last2(rest)
    if len(toks) < 2:
        return None

    def unq(t):
        if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
            return t[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return t
    return pat, unq(toks[0]), unq(toks[1])


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    rules, stats = [], {"jq": 0, "replace": 0, "failed": 0}

    for idx, item in enumerate(data):
        name = "body-rewrite-%03d" % idx
        if item.get("type") == "jq":
            expr = item["expr"]
            try:
                ast = parse(expr)
            except Exception as e:
                stats["failed"] += 1
                rules.append({"n": name, "re": item["pattern"], "err": str(e)[:120]})
                continue
            rules.append({"n": name, "re": item["pattern"], "jq": ast, "e": expr[:200]})
            stats["jq"] += 1
        else:
            pr = parse_replace(item["raw"])
            if not pr:
                stats["failed"] += 1
                continue
            pat, search, rep = pr
            rules.append({"n": name, "re": pat, "rep": [search, rep]})
            stats["replace"] += 1

    rt = open(RT, encoding="utf-8").read()
    rt = re.sub(r"^/\*.*?\*/", "", rt, flags=re.S)

    body = []
    body.append("// 自动生成：由上游 [Body Rewrite] 转换，请勿手改 (tools/gen_scripts.py)")
    body.append(rt.rstrip())
    body.append("")
    body.append("var __RULES__ = " + json.dumps(
        [{"n": r["n"], "p": r["re"], "j": r.get("jq"), "r": r.get("rep")} for r in rules],
        ensure_ascii=False, separators=(",", ":")) + ";")
    body.append("""
function __pick__(url){
  for (var i=0;i<__RULES__.length;i++){
    var r=__RULES__[i];
    try { if (new RegExp(r.p).test(url)) return r; } catch(e){}
  }
  return null;
}
(function(){
  var url = ($request && $request.url) || "";
  var rule = __pick__(url);
  if (!rule || !$response) { $done({}); return; }
  var body = $response.body;
  if (typeof body !== "string") { $done({}); return; }
  if (rule.r) {
    var a = rule.r[0], b = rule.r[1];
    if (a) body = body.split(a).join(b);
    $done({body: body});
    return;
  }
  try {
    var obj = JSON.parse(body);
    var out = JQRT.make(rule.j)(obj);
    $done({body: JSON.stringify(out.length ? out[0] : null)});
  } catch (e) {
    $done({body: body});
  }
})();
""")
    os.makedirs(os.path.join(ROOT, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    js = "\n".join(body)
    open(os.path.join(ROOT, "scripts/body-rewrite.js"), "w", encoding="utf-8").write(js)

    lines = []
    for r in rules:
        if r.get("err"):
            continue
        lines.append("%s = type=http-response, pattern=%s, script-path=%s, requires-body=1, max-size=-1, timeout=20"
                     % (r["n"], r["re"], "__SCRIPT_URL__"))
    open(os.path.join(ROOT, "build/body-rewrite.rules"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(json.dumps({**stats, "script_bytes": len(js.encode()),
                      "rule_count": len([r for r in rules if not r.get("err")])},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
