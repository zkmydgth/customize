# moviepilot/

MoviePilot 侧的**配置外置备份**（本仓库其余内容是 Clash / Shadowrocket 规则集，互不影响）。

| 文件 | 用途 |
|---|---|
| `notification_templates.json` | MoviePilot 通知消息模板（`NotificationTemplates`）当前值导出：含 `setting_key` / 导出时版本 / 日期 / `value`（四套模板原文） |
| `notification_templates.md` | 同上的说明文档：字段字典、应用与回读命令、同步 SOP、回滚、变更记录 |

**改完 MoviePilot 侧模板后，务必同步回来**（否则这份备份会落后，失去防丢失意义）：

```bash
python3 /config/agent/tools/gh_notification_templates.py export      # 从运行配置导出
python3 /config/agent/tools/gh_notification_templates.py push --dry-run
python3 /config/agent/tools/gh_notification_templates.py push --message "chore(notification): <变更>"
```

工具位于 MoviePilot 容器 `/config/agent/tools/gh_notification_templates.py`（鉴权走 MP 已配的 GitHub 凭据，不回显 token；推后用 API 回读核验）。
