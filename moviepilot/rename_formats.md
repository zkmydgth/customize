# MoviePilot 重命名格式（Settings）

> 回指：`主记忆.md` §2 守则（模板/格式类配置的外置备份）与 §6.3 仓库位置表。
> 与 `notification_templates.md` 区分：那份管 **`SystemConfigKey`（存 DB）**，本文件管 **`Settings` 类配置（存 `app.env`）**。

## 一、受管理的四个键与位置

| 键 | MP 界面位置 | 说明 |
|---|---|---|
| `MOVIE_RENAME_FORMAT` | 设定 → 整理 → 电影重命名格式 | 目录层级用 `/` 分隔，末段是文件名 |
| `TV_RENAME_FORMAT` | 设定 → 整理 → 电视剧重命名格式 | 同上 |
| `MUSIC_RENAME_FORMAT` | 设定 → 整理 → 音乐重命名格式 | 专辑 / 碟 / 曲 |
| `RENAME_FORMAT_S0_NAMES` | 设定 → 整理 → S0 别名 | 默认 `["Specials", "SPs"]` |

**当前值以 `rename_formats.json` 为准**（本文件不复制格式正文，避免两处各自演化）。

## 二、重命名格式可用变量（2026-10-10 实测，MP v3.1.3）

重命名格式与通知模板**共用同一个上下文构建器**（`TemplateContextBuilder`，`app/application/messaging/message.py:103`），
所以通知里能用的规格变量在重命名里同样可用。`TransHandler.get_naming_dict` 仅额外移除 `media_source` / `media_id`
（源码注释：重命名格式是独立契约，只保留各数据源原有 ID 变量）。

| 类别 | 变量 |
|---|---|
| 标题身份 | `title` `en_title` `original_title` `name` `en_name` `original_name` `year` `title_year` `type` `category` `customization` |
| 剧集 | `season` `season_fmt` `season_episode` `episode` `part` `total_episodes` `episode_title` `episode_date` |
| 规格 | `webSource`（平台）`resourceType`（WEB-DL/BluRay/REMUX）`videoFormat`（2160p）`videoCodec` `videoBit` `audioCodec` `effect`（HDR/DIY/HQ）`edition` `resource_term` `fps` `releaseGroup` |
| 数据源 ID | `tmdbid` `imdbid` `doubanid` `bangumiid` `anilistid` |
| 其它 | `fileExt`（**必须留在末段**）`vote_average` `actors` `overview` `season_year` `instance_name` |

### 三个已知坑（均为实测）

1. **`resolution` 是恒空的死变量** —— 不在上下文里，写了也不输出（分辨率请用 `videoFormat`）。
2. **帧率正则不认小数点** —— MP 的 `_fps_re = r"(\d{2,3})(?=FPS)"` 会把 `23.976fps` 截成 **`976`**。
   所以写帧率必须加区间保护：`{% if fps and fps|int >= 50 and fps|int <= 120 %}.{{fps}}fps{% endif %}`。
3. **`audioCodec` 会被「媒体数据补充」覆盖** —— 插件对该键是特例：现有值不以「数字.数字」结尾就放行探测值覆盖，
   因此种子名里的 `2Audio(s)` 标记可能被冲掉（`DDP 5.1 2Audio` → 被覆盖；`DDP 5.1`、`…7.1` → 保留）。

## 三、同步 SOP（改完格式必须做）

```bash
# 1) 改格式：走 MoviePilot API（Agent 侧）
#    config.system.update  setting_key=MOVIE_RENAME_FORMAT / TV_RENAME_FORMAT ...  operation=replace
#    带 expected_revision；写后必须用 config.system.get 回读核验
# 2) 从运行配置导出到暂存目录（读 Settings 运行值，不打印任何凭据）
python3 /config/agent/tools/gh_rename_formats.py export
# 3) 预览差异（只读）
python3 /config/agent/tools/gh_rename_formats.py push --dry-run
# 4) 推送（Git Data API 单提交：blobs → tree(base_tree) → commit(parents=main) → PATCH refs/heads/main）
python3 /config/agent/tools/gh_rename_formats.py push --message "chore(rename): <变更>"
```

**只改 MP 设置不推仓库 = 备份失效。**

## 四、回滚

- MP 设定页可直接改回；也可用 `config.system.update`（`operation=replace`）写回旧串。
- 历史版本：本仓库 `moviepilot/rename_formats.json` 的 git 历史（每次改动一次提交）。

## 五、变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-10 | 首次入库：四个键的快照。当日对电影/电视剧格式做了两轮调整 —— ① 质量/规格段补充 `webSource`（平台）、`videoCodec`、`audioCodec`，删除恒空的 `resolution` 段；② 新增 `fps` 段并加 `50–120` 区间保护（规避 `23.976fps → 976` 的解析缺陷） |
