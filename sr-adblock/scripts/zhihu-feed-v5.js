// 2026-01-19 20:50:00

if (!$response.body) $done({});
const url = $request.url;
let obj = JSON.parse($response.body);

if (url.includes("/answers/v2/") || url.includes("/articles/v2/")) {
  // 2024-04-29 新版知乎 回答列表下的相关提问
  if (obj?.third_business?.related_queries?.queries?.length > 0) {
    obj.third_business.related_queries.queries = [];
  }
} else if (url.includes("/api/cloud/zhihu/config/all")) {
  // 全局配置
  if (obj?.data?.configs?.length > 0) {
    for (let i of obj.data.configs) {
      if (i?.configKey === "feed_gray_theme") {
        if (i?.configValue) {
          i.configValue.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
          i.configValue.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
          i.status = false;
        }
      } else if (i?.configKey === "feed_top_res") {
        // 首页顶部背景图
        if (i?.configValue) {
          i.configValue.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
          i.configValue.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
        }
      }
    }
  }
} else if (url.includes("/api/v4/answers")) {
  delete obj.data;
  delete obj.paging;
} else if (url.includes("/api/v4/articles")) {
  const item = ["ad_info", "paging", "recommend_info"];
  item.forEach((i) => {
    delete obj[i];
  });
} else if (url.includes("/appcloud2.zhihu.com/v3/config")) {
  delete obj.config.hp_channel_tab;
  if (obj?.config) {
    if (obj.config?.homepage_feed_tab) {
      obj.config.homepage_feed_tab.tab_infos = obj.config.homepage_feed_tab.tab_infos.filter((i) => {
        if (i.tab_type === "activity_tab") {
          i.start_time = "3818332800"; // Unix 时间戳 2090-12-31 00:00:00
          i.end_time = "3818419199"; // Unix 时间戳 2090-12-31 23:59:59
          return true;
        } else {
          return false;
        }
      });
    }
    if (obj.config?.zombie_conf) {
      obj.config.zombie_conf.zombieEnable = false;
    }
    if (obj.config?.gray_mode) {
      obj.config.gray_modeenable = false;
      obj.config.gray_mode.start_time = "3818332800"; // Unix 时间戳 2090-12-31 00:00:00
      obj.config.gray_mode.end_time = "3818419199"; // Unix 时间戳 2090-12-31 23:59:59
    }
    if (obj.config?.zhcnh_thread_sync) {
      obj.config.zhcnh_thread_sync.LocalDNSSetHostWhiteList = [];
      obj.config.zhcnh_thread_sync.isOpenLocalDNS = "0";
      obj.config.zhcnh_thread_sync.ZHBackUpIP_Switch_Open = "0";
      obj.config.zhcnh_thread_sync.dns_ip_detector_operation_lock = "1";
      obj.config.zhcnh_thread_sync.ZHHTTPSessionManager_setupZHHTTPHeaderField = "1";
    }
    obj.config.zvideo_max_number = 1;
    obj.config.is_show_followguide_alert = false;
  }
} else if (url.includes("/commercial_api/app_float_layer")) {
  // 悬浮图标
  if (obj?.feed_egg) {
    delete obj.feed_egg;
  }
} else if (url.includes("/feed/render/tab/config")) {
  // 首页二级标签 白名单 live直播 edu人工智能AI
  if (obj?.selected_sections?.length > 0) {
    obj.selected_sections = obj.selected_sections.filter((i) => ["recommend", "section"]?.includes(i?.tab_type));
  }
} else if (url.includes("/moments_v3")) {
  if (obj?.data?.length > 0) {
    obj.data = obj.data.filter((i) => !i?.title?.includes("为您推荐"));
  }
} else if (url.includes("/next-bff")) {
  if (obj?.data?.length > 0) {
    obj.data = obj.data.filter(
      (i) =>
        !(
          i?.origin_data?.type?.includes("ad") ||
          i?.origin_data?.resource_type?.includes("ad") ||
          i?.origin_data?.next_guide?.title?.includes("推荐")
        )
    );
  }
} else if (url.includes("/next-data")) {
  if (obj?.data?.data?.length > 0) {
    obj.data.data = obj.data.data.filter((i) => !(i?.type?.includes("ad") || i?.data?.answer_type?.includes("PAID")));
  }
} else if (url.includes("/next-render")) {
  if (obj?.data?.length > 0) {
    obj.data = obj.data.filter(
      (i) =>
        !(
          i?.adjson ||
          i?.biz_type_list?.includes("article") ||
          i?.biz_type_list?.includes("content") ||
          i?.business_type?.includes("paid") ||
          i?.section_info ||
          i?.tips ||
          i?.type?.includes("ad")
        )
    );
  }
} else if (url.includes("/questions/")) {
  // 问题回答列表
  delete obj.ad_info;
  delete obj.data.ad_info;
  delete obj.query_info;
  if (obj?.data?.length > 0) {
    obj.data = obj.data.filter((i) => !i?.target?.answer_type?.includes("paid"));
  }
} else if (url.includes("/root/tab")) {
  // 首页一级标签 白名单
  if (obj?.tab_list?.length > 0) {
    obj.tab_list = obj.tab_list.filter((i) => ["follow", "hot", "recommend"]?.includes(i?.tab_type));
  }
} else if (url.includes("/topstory/hot-lists/everyone-seeing")) {
  // 热榜信息流
  if (obj?.data?.data?.length > 0) {
    // 合作推广
    obj.data.data = obj.data.data.filter((i) => !i.target?.metrics_area?.text?.includes("合作推广"));
  }
} else if (url.includes("/topstory/hot-lists/total")) {
  // 热榜排行榜
  if (obj?.data?.length > 0) {
    // 品牌甄选
    obj.data = obj.data.filter((i) => !i.hasOwnProperty("ad"));
  }
} else if (url.includes("/topstory/recommend")) {
  // 推荐信息流
  if (obj?.data?.length > 0) {
    obj.data = obj.data.filter((i) => {
      if (i.type === "market_card" && i.fields?.header?.url && i.fields.body?.video?.id) {
        let videoID = getUrlParamValue(item.fields.header.url, "videoID");
        if (videoID) {
          i.fields.body.video.id = videoID;
        }
      } else if (i.type === "common_card") {
        if (i.extra?.type === "drama") {
          // 直播内容
          return false;
        } else if (i.extra?.type === "zvideo") {
          // 推广视频
          let videoUrl = i.common_card.feed_content.video.customized_page_url;
          let videoID = getUrlParamValue(videoUrl, "videoID");
          if (videoID) {
            i.common_card.feed_content.video.id = videoID;
          }
        } else if (i.common_card?.feed_content?.video?.id) {
          let search = '"feed_content":{"video":{"id":';
          let str = $response.body.substring($response.body.indexOf(search) + search.length);
          let videoID = str.substring(0, str.indexOf(","));
          i.common_card.feed_content.video.id = videoID;
        } else if (i.common_card?.footline?.elements?.[0]?.text?.panel_text?.includes("广告")) {
          return false;
        } else if (i.common_card?.feed_content?.source_line?.elements?.[1]?.text?.panel_text?.includes("盐选")) {
          return false;
        } else if (i?.promotion_extra) {
          // 营销信息
          return false;
        }
        return true;
      } else if (i.type?.includes("aggregation_card")) {
        // 横排卡片 知乎热榜
        return false;
      } else if (i.type === "feed_advert") {
        // 伪装成正常内容的卡片
        return false;
      }
      return true;
    });
    fixPos(obj.data);
  }
}


// ==== 增强：信息流 / 详情页 广告卡片清理 v3（2026-10-31）====
// 覆盖：首页推荐、回答详情（next-render / answers/v2）、web 版接口
// 依据实测角标：「广告」或「XX的广告」（携程、京东等），只在短标签字段里匹配
try {
  var _isFeed = url.indexOf("/topstory/recommend") >= 0;
  var _isDetail = url.indexOf("/next-") >= 0 || url.indexOf("/answers/") >= 0
                  || url.indexOf("www.zhihu.com/api/v4/answers") >= 0;
  if ((_isFeed || _isDetail) && Array.isArray(obj && obj.data)) {
    obj.data = obj.data.filter(function (i) {
      if (!i) return false;
      var t = String(i.type || "").toLowerCase();
      if (t.indexOf("advert") >= 0 || t.indexOf("promotion") >= 0) return false;
      if (t === "ad" || t.indexOf("_ad_") >= 0) return false;
      if (i.ad_info || i.is_ad || i.adjson) return false;
      if (i.extra && (i.extra.ad_info || i.extra.is_ad)) return false;
      if (i.common_card && i.common_card.ad_info) return false;
      // 角标检测：只取短文本字段，避免误伤正文
      var labels = [];
      ["extra", "header", "footer"].forEach(function (k) {
        var o = i[k];
        if (o && typeof o.text === "string") labels.push(o.text.trim());
        if (o && typeof o.title === "string" && o.title.length <= 12) labels.push(o.title.trim());
      });
      // ① 文案角标：广告 / XX的广告
      for (var n = 0; n < labels.length; n++) {
        var lab = String(labels[n] || "").replace(/\s+/g, "");
        if (!lab) continue;
        if (lab === "广告") return false;
        if (lab.length <= 14 && lab.indexOf("的广告") >= 0) return false;
        if (lab.length <= 14 && lab.indexOf("广告") === 0) return false;
      }
      // ② 激进：没有作者的卡片一律删除（正常回答/文章/视频必然带 author）
      // 广告卡片（倍业/domob/手机淘宝/天猫）都没有 author 字段
      var _hA = !!(i.author || (i.target && i.target.author)
                   || (i.members && i.members.length)
                   || (i.question && i.question.author));
      var _hV = !!(i.voteup_count || (i.target && i.target.voteup_count) || i.reaction_count);
      var _hC = !!(i.comment_count || (i.target && i.target.comment_count));
      if (!_hA && !_hV && !_hC) return false;
      return true;
    });
  }
} catch (e) {}

$done({ body: JSON.stringify(obj) });

// 修复offset
function fixPos(arr) {
  for (let i = 0; i < arr.length; i++) {
    arr[i].offset = i + 1;
  }
}

function getUrlParamValue(url, queryName) {
  return Object.fromEntries(
    url
      .substring(url.indexOf("?") + 1)
      .split("&")
      .map((pair) => pair.split("="))
  )[queryName];
}
