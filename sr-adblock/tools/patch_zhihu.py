#!/usr/bin/env python3
"""拉上游知乎脚本并打补丁，输出到 scripts/zhihu.js

上游 bug（fmz200/wool_scripts，2026-01-19 版）：
  /topstory/recommend 分支里 filter 的形参是 (i)，但有一处调用了
  getUrlParamValue(item.fields.header.url, ...) —— item 未定义。
  一旦推荐流出现 market_card + 视频，就抛 ReferenceError，
  整个 filter 中断、末尾 $done 不执行，原样返回 → 信息流广告清不掉。

本脚本只修这一处，其余逻辑完全跟随上游。
上游若已自行修复（不再出现该写法），脚本只做转存并标记 no_patch_needed，
不会失败也不会改坏。

用法：
  python3 tools/patch_zhihu.py --src /tmp/zhihu.upstream.js --out scripts/zhihu.js
  python3 tools/patch_zhihu.py --url https://raw.githubusercontent.com/.../zhihu.js --out scripts/zhihu.js
"""
import argparse
import json
import os
import sys
import urllib.request

LAUNCH_ANCHOR = 'let obj = JSON.parse($response.body);'

# 开屏广告：知乎把开屏配置放在 body.launch（一个 JSON 字符串）里，
# 形如 {"launch":"{\"ads\":[{...}]}"}。
# 只用 Map Local 返回 {} 会让 App 认为「响应不完整」→ 继续用本地缓存的开屏配置，
# 广告照弹（2026-11-09 日志实证：commercial_api 全部命中 Map Local，启动时零素材下载，
# 但开屏广告仍在显示）。所以这里改成 app2smile 的做法：保持结构合法，只把 ads 清空。
LAUNCH_BLOCK = '''
// [sr-adblock] 开屏广告：清空 launch.ads，并保证 launch 是合法 JSON 字符串
if (url.includes("/commercial_api/real_time_launch_v2") || url.includes("/commercial_api/launch_v2")) {
  try {
    const launch = JSON.parse(obj.launch);
    launch.ads = [];
    obj.launch = JSON.stringify(launch);
  } catch (e) {
    obj = { launch: JSON.stringify({ ads: [] }) };
  }
}
'''

BAD = "getUrlParamValue(item.fields.header.url"
FIXED = "getUrlParamValue(i.fields.header.url"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sr-adblock-build"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def strip_header(text):
    """剥掉上一次补丁留下的头部注释，保证重复执行结果一致"""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (
        lines[i].startswith("// [sr-adblock] patched from")
        or lines[i].startswith("// patch:")
    ):
        i += 1
    return "\n".join(lines[i:])


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--src", help="本地已下载的上游脚本")
    g.add_argument("--url", help="上游脚本 URL")
    ap.add_argument("--out", required=True, help="输出路径")
    ap.add_argument("--report", help="可选：写一份 JSON 报告")
    args = ap.parse_args()

    try:
        if args.url:
            text = fetch(args.url)
        else:
            with open(args.src, encoding="utf-8") as f:
                text = f.read()
    except Exception as e:
        print("PATCH FAIL: 读取上游脚本失败: %s" % e, file=sys.stderr)
        return 1

    if not text.strip():
        print("PATCH FAIL: 上游脚本为空", file=sys.stderr)
        return 1

    text = strip_header(text)
    original_len = len(text)
    hits = text.count(BAD)
    if hits:
        text = text.replace(BAD, FIXED)
        status = "patched"
    else:
        status = "no_patch_needed"

    # 断言：不允许再有未修复的调用；也不允许把别的 item 用法改坏
    if BAD in text:
        print("PATCH FAIL: 补丁后仍存在 %s" % BAD, file=sys.stderr)
        return 1
    # 上游 /api/v4/articles 分支里的 `const item = [...]` 必须保持原样
    if "const item = [" not in text:
        print("PATCH FAIL: 上游结构变化（const item = [...] 不存在），需人工确认", file=sys.stderr)
        return 1

    # 注入开屏广告处理（幂等：已注入则跳过）
    launch_added = False
    if "[sr-adblock] 开屏广告" in text:
        launch_added = False
    elif LAUNCH_ANCHOR in text:
        text = text.replace(LAUNCH_ANCHOR, LAUNCH_ANCHOR + "\n" + LAUNCH_BLOCK.rstrip("\n"), 1)
        launch_added = True
    else:
        print("PATCH WARN: 找不到 %s，跳过开屏注入（需人工确认上游结构）" % LAUNCH_ANCHOR, file=sys.stderr)

    header = (
        "// [sr-adblock] patched from fmz200/wool_scripts Scripts/zhihu/zhihu.js\n"
        "// patch: getUrlParamValue(item.fields...) -> (i.fields...)\n"
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(header + text)

    info = {
        "status": status,
        "patched_occurrences": hits,
        "launch_injected": launch_added,
        "upstream_bytes": original_len,
        "output_bytes": os.path.getsize(args.out),
    }
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    print("PATCH %s: %s (%d 处) -> %s" % (status.upper(), status, hits, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
