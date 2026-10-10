# MoviePilot 通知模板（NotificationTemplates）

> 本目录是 **MoviePilot 通知消息模板的唯一外置备份**。容器侧实际生效值是数据库
> `systemconfig` 表的 `NotificationTemplates` 键（界面位置：**设定 → 通知 → 通知模板**）。
> 本仓库这份用于**防丢失 + 版本留痕**：改动后按下面 SOP 同步过来。

- 导出环境：MoviePilot `v3.1.3`，Docker（overlayfs），通知渠道 Telegram（Rich Message）
- 文件：
  - `notification_templates.json` —— 机器可读，含 `setting_key` / `moviepilot_version_at_write` / `updated_at` / `value`（四个模板原文）
  - `notification_templates.md` —— 本文档：字段说明、应用/回读命令、同步 SOP、变更记录

## 一、四个模板与键名

| 键名 | 对应通知 | 说明 |
|---|---|---|
| `organizeSuccess` | 📂 资源入库（整理成功） | 含失败原因（`err_msg`） |
| `downloadAdded` | 📥 资源下载（开始下载） | 含种子信息 |
| `subscribeAdded` | 🎞 添加订阅 | |
| `subscribeComplete` | 🏆 订阅完成 | 标题按 `msgstr` 显示「订阅 / 洗版」 |

模板是 **Python 字面量 dict**（`{'title': ..., 'text': ...}`），渲染时按字段独立做过 Jinja2 —
因此 `{% if type == "音乐" %}` 这类**带引号条件不会被转义**（旧版整体 `json.dumps` 才会转义）。
`\n` 保留为转义序列，渲染后换行。

## 二、本套模板的本地增强（相对官方示例）

1. **季集显示**：`{{ season_episode | replace(season_fmt, season_fmt ~ " ") }}` → `S01 E05`、`S01 E01-E02`、`S01-S03 E01-E12`
2. **整季兜底**：无集号时 `S01 全集`；`category` 含「综艺」时显示 `S03 整季`
3. **长文本截断**：描述 `truncate(160)`、简介 `truncate(200)`、失败原因 `truncate(120)`，避免撑爆 Telegram 4096 字符
4. **订阅完成按 `msgstr`**：显示「已完成订阅」或「已完成洗版」
5. **链接**：标题为可点击 Markdown 链接（TMDB 详情页）；订阅通知额外给 `IMDb` / `豆瓣`（有 ID 才显示）
6. **标题加粗**：`**[片名 (年份)](链接)**`
7. **规格补全**：`videoCodec` / `fileExt` / `fps` / 分段 `part`（`edition` 不再单列 —— 内容与质量行重复，2026-10-10 删除）
   - ⚠️ 质量行只用 `resource_term` + `videoCodec` + `audioCodec`，**不要**再单独输出 `resourceType`：
     `resource_term = resourceType + effect + videoFormat` 已包含它，重复输出会出现两个 `WEB-DL`（2026-10-10 修复）。
8. **下载保留 PT 关键项**：`volume_factor`（促销）、`freedate`（免费剩余）

## 三、可用变量（v3.1.x 实测）

- 媒体：`type` `title` `en_title` `original_title` `title_year` `year` `season` `season_fmt` `season_year`
  `category` `vote_average` `poster` `backdrop` `actors` `overview` `tmdbid` `imdbid` `doubanid`
  `bangumiid` `anilistid` `media_source` `media_id`
- 文件/识别：`original_name` `name` `en_name` `episode` `total_episodes` `season_episode` `part`
  `fps` `episode_title` `episode_date` `customization`
- 规格：`resourceType` `effect` `edition` `videoFormat` `videoBit` `videoCodec` `audioCodec`
  `webSource` `resource_term` `releaseGroup`
- 种子：`torrent_title` `pubdate` `freedate` `seeders` `volume_factor` `hit_and_run` `labels` `description` `site_name` `size`
- 整理：`transfer_type` `file_count` `total_size` `err_msg`；文件后缀 `fileExt`
- 音乐：`artist` `artists` `album` `album_artist` `track` `track_number` `total_tracks` `disc_number`
  `duration` `isrc` `version` `audio_format` `audio_lossless` `audio_quality` `audio_specs`
  `bit_depth` `sample_rate` `sample_rate_khz` `bitrate` `bitrate_kbps`
- 原始对象：`__meta__` `__mediainfo__`（含 `detail_link`）`__torrentinfo__`（含 `page_url`）`__transferinfo__` `__episodes_info__`
- 调用方附加：`msgstr`（订阅完成：订阅/洗版）、`username`、`instance_name`

**本版本无来源、写了也不会出现**：`download_episodes`、`username`（订阅通知里那行不会渲染）。
`episode_title` / `episode_date` 取决于调用方是否带 `episodes_info`，取不到时模板里 `{% if %}` 会整段省略。

## 四、同步 SOP（改完模板必须做）

```bash
# 1) 改模板：走 MoviePilot API（agent 侧）
#    config.system.update  setting_key=NotificationTemplates  operation=merge_dict  value={...}
#    （带 expected_revision，写后必须用 config.system.get 回读核验）

# 2) 从运行配置导出到暂存目录（读 DB，不打印任何凭据）
python3 /config/agent/tools/gh_notification_templates.py export

# 3) 预览差异（只读）
python3 /config/agent/tools/gh_notification_templates.py push --dry-run

# 4) 推送（Git Data API 单提交：blobs → tree(base_tree) → commit(parents=main) → PATCH refs/heads/main）
python3 /config/agent/tools/gh_notification_templates.py push \
  --message "chore(notification): 更新通知模板（<一句话变更>）"
```

- 推后核验走 **GitHub API（不是 raw —— raw 有 CDN 缓存）**，脚本已内置逐文件 blob sha 比对。
- 本仓库**无 CI、不发 Release**，推上去即可用（本文件仅作备份，不参与客户端拉取）。

## 五、回滚

- 容器侧最近一版老模板备份：`/config/temp/notification_templates_backup_2026-10-10.json`（可直接 `merge_dict` 写回）。
- 历史版本：本仓库 `moviepilot/notification_templates.json` 的 git 历史（每次改动一次提交）。

## 六、变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-10 | 首次入库：换用新版四模板（emoji + 可点击标题 + 音乐字段），并完成本地增强：季集空格版 `S01 E01-E02`、整季兜底「全集/整季」、描述/简介/失败截断、订阅完成按 `msgstr`、IMDb/豆瓣链接、标题加粗、规格补全（`videoCodec`/`edition`/`fileExt`/`fps`/`part`）、下载恢复 `volume_factor`/`freedate` |
| 2026-10-10 | 修复质量行重复：`downloadAdded` / `organizeSuccess` 的质量行删去冗余的 `{% if resourceType %}{{ resourceType }} {% endif %}`，输出由 `WEB-DL WEB-DL 2160p H265 DDP 2.0` 变为 `WEB-DL 2160p H265 DDP 2.0`；`版本` 行按要求保留。核验：`config.system.get` 回读 + 模板渲染实测 |
| 2026-10-10 | 删除「版本」行（此前同日曾按要求保留，现按要求移除）：`downloadAdded` / `organizeSuccess` 去掉 `{% if edition %}\n🧾 版本：{{ edition }}{% endif %}` 整行 —— `edition` 的内容已含在质量行（`webSource` + `resource_term` + 编解码）中。其余行、另两个模板均未改动。核验：`config.system.get` 回读逐字节比对（仅少该行，两模板各 62 字符）+ Jinja 渲染实测 |
