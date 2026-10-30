# sr-adblock · Shadowrocket 完整适配版

把 [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts) 的 **Surge 去广告模块**（`blockAds.module`）
转换成 **Shadowrocket 可用**的模块，**包含上游的 `[Body Rewrite]`**（jq 表达式编译成 JS），
并每天自动同步上游更新。

- 上游：`Surge/module/blockAds.module`
- 产物：`dist/blockAds.sr.module`
- 更新：GitHub Actions 每天 04:00（北京）拉取 → 转换 → **验证** → 提交；也可手动触发

## 在 Shadowrocket 里使用

```
https://raw.githubusercontent.com/zkmydgth/customize/main/sr-adblock/dist/blockAds.sr.module
```

1. Shadowrocket → 「配置」→ 右上 `+` → 类型选 **模块 / Module** → 粘贴上面的 URL → 保存
2. 确认模块已启用，返回首页打开代理开关
3. 安装并信任证书：设置 → 通用 → VPN与设备管理 → 安装；
   设置 → 通用 → 关于本机 → 证书信任设置 → 对 Shadowrocket 证书开启完全信任
4. 部分 App 需清缓存或重装才生效（广告 SDK 有本地缓存）

更新：点进模块 → 更新（或删掉重新添加 URL）。

## 转换对照

| 上游段落 | 处理 | 条数（2026-10-25 版） |
|---|---|---|
| `[Rule]` | 原样保留 | 2974（含 `IP-CIDR6` 3 条） |
| `[URL Rewrite]` | 原样保留 | 518 |
| `[Map Local]` | `tiny-gif` → URL Rewrite 的 `reject-tinygif`；`data-type=file` 丢弃；修正 `^http?:` 笔误 | 714 (+101) |
| `[Script]` | 保留；去掉 `argument=`；`requires-body` 归一 | 224 |
| `[Body Rewrite]` | **jq / 字符串替换 → 编译成 `scripts/body-rewrite.js`** | **96 → 全部生效** |
| `[MITM]` | 去 `%APPEND%`、去重、补全脚本所需域名 | 943 |
| `[General]` | 丢弃（SR 不认 `force-http-engine-hosts`） | 1 |
| `#!arguments` | 丢弃（SR 无模块参数机制） | 1 |

### Body Rewrite 是怎么“救回来”的

上游 96 条分两类：

- **24 条纯字符串替换**（`false`→`true`、`"list":[...]`→`"list":[]`）→ 编译成 `String.split().join()`
- **72 条 jq 表达式**（`del(.data.payment)`、`map(select(...))`）→ `tools/jqparse.py` 解析成 AST，
  `tools/jq_runtime.js` 求值，全部合并进**一个** `scripts/body-rewrite.js`（约 58 KB）

模块里追加 96 行 `[Script]`，全部指向同一个脚本，脚本按 `$request.url` 匹配规则。
这样只加载一份运行时，而不是 96 个独立文件。

## 验证（每次同步都会跑，失败则不提交）

| 检查 | 方法 | 结果 |
|---|---|---|
| jq 语义等价 | `tools/test_equiv.py`：同一条表达式分别交给官方 `jq` 与 JS 运行时，在 6 组随机输入上比对 | 568 例全一致（允许双方都报错的类型擦边） |
| 脚本端到端 | `tools/test_script.js`：模拟 `$request/$response/$done` 跑真实 URL + 响应 | 7/7 通过 |
| 结构健全 | Rule > 2000、Script > 300、无 `[Body Rewrite]` 段、MITM 存在 | 通过 |

本地复现：

```bash
apk add jq nodejs            # 或 apt install jq nodejs
python3 tools/extract_body.py upstream.module /tmp/bodyrewrite.json
python3 tools/convert.py upstream.module dist/blockAds.sr.module
python3 tools/gen_scripts.py
python3 tools/assemble.py --module dist/blockAds.sr.module \
  --rules build/body-rewrite.rules --script-url <脚本 raw URL>
python3 tools/test_equiv.py --inputs 6
node tools/test_script.js
```

## 已知边界

- `[Header Rewrite]` 1 条（B 站 gRPC）SR 无对应段，未转换
- 9 个引用 `argument` 的上游脚本拿不到参数（SR 无模块参数），行为按默认值走
- 少数上游脚本使用 Surge 专有 `$task.fetch`，SR 不支持，运行时会报错（脚本自身问题）
- `IP-CIDR` 只覆盖 IPv4；域名规则不受 IPv6 影响
- 上游若写出语法错误，`test_equiv.py` 会失败并阻止提交

## 版权

规则与脚本版权归 fmz200 及各原作者，本仓库只做格式适配与自动同步，不修改规则语义
（唯一例外：容忍上游的尾逗号、修正 `^http?:` 正则笔误）。
