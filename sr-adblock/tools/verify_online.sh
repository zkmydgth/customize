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
for f in blockAds.sr.module blockAds.full.srmodule unlock.srmodule all-in-one.srmodule; do
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
# 解锁类产物用各自的断言
if [ -s "$TMP/unlock.srmodule" ]; then
  printf '%-26s ' "unlock.srmodule:"
  if python3 tools/dz_check.py --module "$TMP/unlock.srmodule" --min-rule 0 --min-urw 0 \
       --min-script 100 --min-mitm 100 > /dev/null; then echo "CHECK PASS"; else echo "CHECK FAIL"; FAIL=1; fi
fi
if [ -s "$TMP/all-in-one.srmodule" ]; then
  printf '%-26s ' "all-in-one.srmodule:"
  if python3 tools/health_check.py --module "$TMP/all-in-one.srmodule" > /dev/null; then echo "HEALTH PASS"; else echo "HEALTH FAIL"; FAIL=1; fi
fi

if [ "$NO_CMP" = "0" ]; then
  echo
  echo "--- 与本地 dist 字节比对（仅当本地是同一上游构建时有效）---"
  for pair in "dist/blockAds.sr.module:$TMP/blockAds.sr.module" \
              "dist/blockAds.full.srmodule:$TMP/blockAds.full.srmodule" \
              "dist/unlock.srmodule:$TMP/unlock.srmodule" \
              "dist/all-in-one.srmodule:$TMP/all-in-one.srmodule"; do
    L=${pair%%:*}; R=${pair##*:}
    [ -f "$L" ] || { echo "  - $L 不存在，跳过"; continue; }
    # 「生成时间」行每次构建都不同，比较前剔除，避免误报不一致
    grep -v '#  生成时间:' "$L" > "$TMP/l.f" 2>/dev/null || : > "$TMP/l.f"
    grep -v '#  生成时间:' "$R" > "$TMP/r.f" 2>/dev/null || : > "$TMP/r.f"
    if cmp -s "$TMP/l.f" "$TMP/r.f"; then
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
