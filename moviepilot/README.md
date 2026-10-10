# moviepilot/

MoviePilot 侧的**配置外置备份**（本仓库其余内容是 Clash / Shadowrocket 规则集，互不影响）。

| 文件 | 用途 |
|---|---|
| `notification_templates.json` / `.md` | MoviePilot 通知消息模板（`NotificationTemplates`，**SystemConfigKey，存 DB**）的当前值导出 + 说明文档（字段字典、同步 SOP、回滚、变更记录） |
| `rename_formats.json` / `.md` | MoviePilot **重命名格式**（`MOVIE_RENAME_FORMAT` / `TV_RENAME_FORMAT` / `MUSIC_RENAME_FORMAT` / `RENAME_FORMAT_S0_NAMES`，**Settings，存 app.env**）的当前值导出 + 说明文档（可用变量清单、三个已知坑、同步 SOP、回滚、变更记录） |

**改完 MoviePilot 侧的通知模板或重命名格式后，务必同步回来**（否则这份备份会落后，失去防丢失意义）：

```bash
# 通知模板（SystemConfigKey / DB）
python3 /config/agent/tools/gh_notification_templates.py export
python3 /config/agent/tools/gh_notification_templates.py push --dry-run
python3 /config/agent/tools/gh_notification_templates.py push --message "chore(notification): <变更>"

# 重命名格式（Settings / app.env）
python3 /config/agent/tools/gh_rename_formats.py export
python3 /config/agent/tools/gh_rename_formats.py push --dry-run
python3 /config/agent/tools/gh_rename_formats.py push --message "chore(rename): <变更>"
```

两个工具都在 MoviePilot 容器 `/config/agent/tools/`（鉴权走 MP 已配的 GitHub 凭据，不回显 token；推后用 API 回读核验）。
