#!/bin/sh
# 推送后核对：从线上拉回产物，确认新增屏蔽规则没被构建脚本改动或吞掉
# 用法：sh tools/verify_online.sh [--no-cmp]
set -u
cd "$(dirname "$0")/.." || exit 1

RAW="https://raw.githubusercontent.com/zkmydgth/customize/main/sr-adblock/dist"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAIL=0

echo "拉取线上产物..."
for f in blockAds.sr.module blockAds.full.srmodule; do
  curl -sSL --http1.1 --max-time 60 "$RAW/$f" -o "$TMP/$f" 2>/dev/null
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

if [ "${1:-}" != "--no-cmp" ]; then
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
      echo "    若本地是旧构建，属正常；否则查：上游是否刚更新 / CI 是否 checkout 旧 commit"
    fi
  done
fi

echo
[ "$FAIL" = "0" ] && echo "RESULT: PASS" || echo "RESULT: FAIL"
exit "$FAIL"
