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
import repair

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bodyrewrite.json"
OUT_ROOT = sys.argv[2] if len(sys.argv) > 2 else None
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
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    rules, stats = [], {"jq": 0, "replace": 0, "failed": 0}
    unhandled = []

    for idx, item in enumerate(data):
        name = "body-rewrite-%03d" % idx
        if item.get("type") == "jq":
            expr = item["expr"]
            try:
                ast = parse(expr)
            except Exception as e:
                stats["failed"] += 1
                unhandled.append({"name": name, "pattern": item["pattern"][:160], "reason": str(e)[:120]})
                continue
            pat2, ch1, _ = repair.fix_scheme(item["pattern"])
            if ch1:
                stats["scheme_fixed"] = stats.get("scheme_fixed", 0) + 1
            if not repair.pattern_compiles(pat2):
                unhandled.append({"name": name, "pattern": pat2[:160], "reason": "pattern 无法编译"})
                stats["failed"] += 1
                continue
            rules.append({"n": name, "re": pat2, "jq": ast, "e": expr[:200]})
            stats["jq"] += 1
        else:
            pr = parse_replace(item["raw"])
            if not pr:
                stats["failed"] += 1
                continue
            pat, search, rep = pr
            pat2, ch1, _ = repair.fix_scheme(pat)
            if ch1:
                stats["scheme_fixed"] = stats.get("scheme_fixed", 0) + 1
            rules.append({"n": name, "re": pat2, "rep": [search, rep]})
            stats["replace"] += 1

    with open(RT, encoding="utf-8") as f:
        rt = f.read()
    rt = re.sub(r"^/\*.*?\*/", "", rt, flags=re.S)

    body = []
    body.append("// 自动生成：由上游 [Body Rewrite] 转换，请勿手改 (tools/gen_scripts.py)")
    body.append(rt.rstrip())
    body.append("")
    body.append("var __RULES__ = " + json.dumps(
        [{"n": r["n"], "p": r["re"], "j": r.get("jq"), "r": r.get("rep")} for r in rules],
        ensure_ascii=False, separators=(",", ":")) + ";")
    body.append("""
function __rx(p){
  var flags = "";
  while (p.indexOf("(?i)") === 0) { flags += "i"; p = p.slice(4); }
  try { return new RegExp(p, flags); } catch (e) { return null; }
}
var __RE__ = [];
for (var __i = 0; __i < __RULES__.length; __i++) __RE__.push(__rx(__RULES__[__i].p));

(function () {
  var url = ($request && $request.url) || "";
  var body = $response && $response.body;
  if (typeof body !== "string") { $done({}); return; }

  // 同一 URL 可能命中多条规则（上游大量重复 pattern），必须全部依次应用
  var matched = [];
  for (var i = 0; i < __RULES__.length; i++) {
    if (__RE__[i] && __RE__[i].test(url)) matched.push(__RULES__[i]);
  }
  if (!matched.length) { $done({}); return; }

  var obj = undefined;   // undefined=未解析 / null=解析失败
  for (var k = 0; k < matched.length; k++) {
    var r = matched[k];
    if (r.r) {                                  // 字符串替换
      if (r.r[0]) body = body.split(r.r[0]).join(r.r[1]);
      obj = undefined;                          // 字符串已变，需重新解析
      continue;
    }
    if (!r.j) continue;
    if (obj === undefined) {
      try { obj = JSON.parse(body); } catch (e) { obj = null; }
    }
    if (obj === null) continue;
    try {
      var out = JQRT.make(r.j)(obj);
      if (out.length && out[0] !== undefined) obj = out[0];
    } catch (e) { /* 单条失败不影响其他规则 */ }
  }
  if (obj !== undefined && obj !== null) body = JSON.stringify(obj);
  $done({ body: body });
})();
""")
    root = OUT_ROOT or ROOT
    os.makedirs(os.path.join(root, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(root, "build"), exist_ok=True)
    js = "\n".join(body)
    with open(os.path.join(root, "scripts/body-rewrite.js"), "w", encoding="utf-8") as f:
        f.write(js)

    lines = []
    for r in rules:
        if r.get("err"):
            continue
        lines.append("%s = type=http-response, pattern=%s, script-path=%s, requires-body=1, max-size=-1, timeout=20"
                     % (r["n"], r["re"], "__SCRIPT_URL__"))
    with open(os.path.join(root, "build/body-rewrite.rules"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    rep = {**stats, "script_bytes": len(js.encode()),
           "rule_count": len([r for r in rules if not r.get("err")]),
           "unhandled": unhandled}
    with open(os.path.join(root, "build/report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
