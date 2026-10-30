#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自适配测试：模拟上游「新增段 / 新规则类型 / 写坏语法 / 动作错位」时，
转换流程必须不崩溃、把无法处理的项记录下来，而不是静默丢弃；能修的必须修好。
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

FIXTURE = r"""#!name=fake upstream
#!date=2026-01-01 00:00:00

[General]
some-new-key = 1

[Rule]
DOMAIN,keep-me.example,REJECT
DOMAIN-SUFFIX,keep2.example,REJECT
BRAND-NEW-RULE-TYPE,foo.example,SOME-POLICY
DOMAIN,misplaced.example.com-NO-DROP,REJECT

[URL Rewrite]
^https?:\/\/rw\.example\.com\/a - reject
http:\/\/rw2\.example\.com\/b - reject

[Map Local]
^https?:\/\/ml\.example\.com\/c data-type=text data="{}" status-code=200
^https:\/\/ml2\.example\.com data-type=tiny-gif status-code=200

[Body Rewrite]
http-response-jq ^https:\/\/ok\.example\.com\/1 'del(.ad)'
http-response-jq ^https:\/\/bad\.example\.com\/2 'del(.ad'
http-response-jq [broken-regex 'del(.ad)'
http-response ^https:\/\/rep\.example\.com\/3 old new

[Brand New Section]
whatever = 1
another = 2

[MITM]
hostname = %APPEND% ok.example.com, bad.example.com
"""


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():  # noqa: C901
    fails = []
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "upstream.module")
        with open(src, "w", encoding="utf-8") as f:
            f.write(FIXTURE)
        out = os.path.join(td, "out.module")
        rep = os.path.join(td, "report.json")

        p = run([sys.executable, "tools/convert.py", src, out, "--report", rep])
        if p.returncode != 0:
            fails.append("convert 崩溃: " + (p.stderr or "")[-300:])
        else:
            with open(rep, encoding="utf-8") as f:
                d = json.load(f)
            if "Brand New Section" not in d.get("unknown_sections", {}):
                fails.append("未知段未被记录: %r" % d.get("unknown_sections"))
            with open(out, encoding="utf-8") as f:
                txt = f.read()
            if "BRAND-NEW-RULE-TYPE,foo.example,SOME-POLICY" not in txt:
                fails.append("新规则类型被丢弃（应原样保留）")
            plain = txt.replace("\\", "")
            for k in ("keep-me.example", "keep2.example", "ml.example.com", "rw.example.com"):
                if k not in plain:
                    fails.append("正常规则丢失: " + k)
            if "DOMAIN,misplaced.example.com,REJECT-NO-DROP" not in txt:
                fails.append("动作后缀错位未修复")
            if "misplaced.example.com-NO-DROP" in txt:
                fails.append("错位域名仍残留")
            if "reject-tinygif" not in txt:
                fails.append("tiny-gif 未转换")
            mitm = [l for l in txt.split("\n") if l.lower().startswith("hostname")]
            if not mitm or any("%APPEND%" in l for l in mitm):
                fails.append("MITM 的 %%APPEND%% 未清理: " + repr(mitm))
            if r"https?:\/\/rw2" not in txt:
                fails.append("http:// 笔误未修正")

        p = run([sys.executable, "tools/extract_body.py", src, "/tmp/adapt_body.json"])
        if p.returncode != 0:
            fails.append("extract 崩溃: " + (p.stderr or "")[-200:])
        else:
            gsroot = os.path.join(td, "gen")
            os.makedirs(os.path.join(gsroot, "build"), exist_ok=True)
            p = run([sys.executable, "tools/gen_scripts.py", "/tmp/adapt_body.json", gsroot])
            rp = os.path.join(gsroot, "build", "report.json")
            if p.returncode != 0:
                fails.append("gen_scripts 崩溃: " + (p.stderr or "")[-300:])
            elif os.path.exists(rp):
                with open(rp, encoding="utf-8") as f:
                    r = json.load(f)
                if len(r.get("unhandled", [])) < 2:
                    fails.append("坏条目未被记录为 unhandled（实际 %d 条）"
                                 % len(r.get("unhandled", [])))
                if r.get("jq", 0) < 1:
                    fails.append("正常 jq 规则未生成")
                if r.get("replace", 0) < 1:
                    fails.append("字符串替换规则未生成")

    if fails:
        print("ADAPT FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("ADAPT PASS: 新段记录 / 新类型保留 / 坏语法进 unhandled / 动作错位修复 / 正常规则不受影响")
    return 0


if __name__ == "__main__":
    sys.exit(main())
