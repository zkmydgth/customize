#!/bin/sh
# 推送后核对：从线上拉回产物，确认新增屏蔽规则没被构建脚本改动或吞掉
# 用法：sh tools/verify_online.sh [--no-cmp] [--strict]
#   --no-cmp  跳过本地与线上字节比对（本地刚改完还没重建时用）
#   --strict  字节不一致也算失败（发布核对时建议加上）
set -u
cd "$(dirname "$0")/.." || exit 1

NO_CMP=0
STRICT=0
for a in "$@"; do
  case "$a" in
    --no-cmp) NO_CMP=1 ;;
    --strict) STRICT=1 ;;
    *) echo "未知参数: $a"; exit 2 ;;
  esac
done

RAW="https://raw.githubusercontent.com/zkmydgth/customize/main/sr-adblock/dist"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAIL=0
CMP_WARN=0

echo "拉取线上产物..."
for f in blockAds.sr.module blockAds.full.srmodule; do
  # -f：404/500 时不要保存错误页面当成模块
  curl -fsSL --http1.1 --max-time 60 "$RAW/$f" -o "$TMP/$f" 2>/dev/null
  if [ ! -s "$TMP/$f" ]; then
    echo "  ✗ $f 下载失败"; FAIL=1; continue
  fi
  echo "  ✓ $f $(wc -c < "$TMP/$f") B"
done

echo
echo "--- 补充规则逐条核对（extra_rules.txt 必须全部在线上产物里）---"
for f in blockAds.sr.module blockAds.full.srmodule; do
  [ -s "$TMP/$f" ] || continue
  printf '%-26s ' "$f:"
  if python3 tools/check_extra.py --module "$TMP/$f"; then :; else FAIL=1; fi
done

if [ "$NO_CMP" = "0" ]; then
  echo
  echo "--- 与本地 dist 字节比对（仅当本地是同一上游构建时有效）---"
  for pair in "dist/blockAds.sr.module:$TMP/blockAds.sr.module" \
              "dist/blockAds.full.srmodule:$TMP/blockAds.full.srmodule"; do
    L=${pair%%:*}; R=${pair##*:}
    [ -f "$L" ] || { echo "  - $L 不存在，跳过"; continue; }
    if cmp -s "$L" "$R"; then
      echo "  ✓ $(basename "$L") 字节一致"
    else
      echo "  ! $(basename "$L") 不一致（本地 $(wc -c < "$L") B / 线上 $(wc -c < "$R") B）"
      echo "    查：上游是否刚更新 / CI 是否 checkout 旧 commit / 本地是否漏重建"
      CMP_WARN=1
    fi
  done
fi

echo
if [ "$FAIL" != "0" ]; then
  echo "RESULT: FAIL"
  exit 1
fi
if [ "$CMP_WARN" != "0" ]; then
  if [ "$STRICT" = "1" ]; then
    echo "RESULT: FAIL（--strict：字节不一致）"
    exit 1
  fi
  echo "RESULT: PASS（警告：字节不一致，加 --strict 可判为失败）"
  exit 0
fi
echo "RESULT: PASS"
exit 0
