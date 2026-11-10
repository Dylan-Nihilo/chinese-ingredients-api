# 数据来源与维护说明

## 版本和许可

本版数据集为 `0.1.0`，结构版本为 `1.0.0`，核验日期为 **2026-11-10**。包含 **18 个食材、4 个厨房用途分类**。这是一个有明确来源的小型起步词表，不是完整中国食材数据库。

`data/` 中的名称事实来自 Wikidata 的 CC0 结构化数据。项目原创的选择、分类及编辑内容同样以 **CC0-1.0** 提供。代码的 MIT 许可与数据的 CC0 许可分别适用；它们不会改变其他第三方内容的原有权利。

已单独打开并核对 [Wikidata Licensing](https://www.wikidata.org/wiki/Wikidata:Licensing)：主名字空间等结构化数据使用 CC0；其他名字空间文本、Wikipedia 文章、Commons 图片不因此成为 CC0。本版未导入文章、描述或媒体。

## 核验方法

使用网页读取工具直接打开 Wikidata 实体页面并定位中文名称；核对的内容是 `taxon common name` 结构化陈述或 Wikidata 内保存的站点链接标题。没有将 Wikipedia 文章正文作为数据来源。每条食材的 `sourceRefs` 记录实体 URL、访问日期、支持字段及核验位置。

遇到实体重定向时已读取返回页面的永久链接，保存最终实体：黄瓜 Q12835405 → Q23425，茄子 Q13144229 → Q7540，豌豆 Q31696297 → Q25237。

名称来源清单：

| 本项目名称 | 已核对实体 | 证据类型 | 本版别名 |
| --- | --- | --- | --- |
| 土豆 | [Q10998](https://www.wikidata.org/wiki/Q10998) | taxon common name | 马铃薯、洋芋 |
| 番茄 | [Q23501](https://www.wikidata.org/wiki/Q23501) | taxon common name | 西红柿 |
| 黄瓜 | [Q23425](https://www.wikidata.org/wiki/Q23425) | taxon common name | 无 |
| 茄子 | [Q7540](https://www.wikidata.org/wiki/Q7540) | taxon common name | 无 |
| 胡萝卜 | [Q81](https://www.wikidata.org/wiki/Q81) | 中文站点链接标题 | 无 |
| 菠菜 | [Q81464](https://www.wikidata.org/wiki/Q81464) | taxon common name | 无 |
| 生菜 | [Q83193](https://www.wikidata.org/wiki/Q83193) | taxon common name | 无 |
| 花椰菜 | [Q7537](https://www.wikidata.org/wiki/Q7537) | taxon common name | 菜花 |
| 冬瓜 | [Q652206](https://www.wikidata.org/wiki/Q652206) | taxon common name | 无 |
| 苦瓜 | [Q428750](https://www.wikidata.org/wiki/Q428750) | taxon common name | 凉瓜 |
| 洋葱 | [Q23485](https://www.wikidata.org/wiki/Q23485) | taxon common name | 无 |
| 甘薯 | [Q37937](https://www.wikidata.org/wiki/Q37937) | taxon common name | 无 |
| 豌豆 | [Q25237](https://www.wikidata.org/wiki/Q25237) | taxon common name | 无 |
| 香菇 | [Q320999](https://www.wikidata.org/wiki/Q320999) | taxon common name | 无 |
| 平菇 | [Q186451](https://www.wikidata.org/wiki/Q186451) | 中文站点链接标题 | 无 |
| 猪肉 | [Q191768](https://www.wikidata.org/wiki/Q191768) | 吴语站点链接标题 | 无 |
| 牛肉 | [Q192628](https://www.wikidata.org/wiki/Q192628) | 中文站点链接标题 | 无 |
| 花生 | [Q37383](https://www.wikidata.org/wiki/Q37383) | taxon common name | 无 |

这些是名称事实的来源，不是食材实体与生物分类单元的 `sameAs` 关系。植物和真菌实体可能涵盖非食用部分。本 API 的食材概念、ID、首选显示名称、是否收录及厨房用途分类是项目自行整理。`sourceRefs.fields` 不把这些编辑选择伪装成来源事实。

## 范围与局限

- 只包括食材，不包括调料、盐、糖、油、酱料或香辛料。葱姜蒜等边界条目暂不加入；洋葱按常见蔬菜用途收录。
- 当前不覆盖所有蔬菜、禽肉、禽蛋、乳品、豆制品、水产、谷物和地域食材。少量已核验条目优先于大量未经核验的来源标注。
- 全部 `description` 和 `icon` 为 `null`。没有复制食谱、营养成分表、商业图片或第三方图标。
- Wikidata 可随时更新；访问日期仅表示此次核对时间。本版未固定所有上游 revision，也不保证上游内容正确。接受带证据的纠错。
- 名称收录不能用来鉴别野生菌、认定食用安全、判断保护状态或提供医疗营养建议。
- 调研过但未验证开放许可的政府目录不包含在公开数据集内。其词表、分类和文档未作为本版发布内容；每个留下的名称与别名均在上述 CC0 来源重新核验。

## 别名规则

别名必须是已核验的词汇名称，不把部位、切法、加工状态、品牌或品种无区别合并。`locale: zh-CN` 是本版使用的简体中文语境标记，不声称该词在各地区含义完全相同。

例如不把“肉末”作为猪肉别名，不把“娃娃菜”当作所有大白菜的同义词，不把鲜毛豆与成熟大豆合并。空别名列表表示本版尚未纳入，而非该食材没有别名。

未来允许多个条目共享一个别名。搜索应返回候选集合，不能把别名设为全局唯一键；“土豆”等词在不同地区也可能指其他食材。本版明确采用大陆烹饪语境下的土豆概念。

## ID 与后续贡献

已有 ID 保持稳定且不承载类别、语言或排序含义。本版保留已分配的登记编号，因此 ID 有间隔；这不是数据缺失错误。`ing_000001` 至 `ing_000064` 已登记或预留，下一新增编号从 `ing_000065` 开始。不得根据当前数组位置或名称排序重新分配 ID，不得把旧 ID 用于另一种食材。

改名、更新别名、修正分类不改变 ID。合并或弃用时需保留历史映射并设计重定向；本版尚未提供此类运行时功能。

新增数据应：

1. 核验确实属于第一阶段食材范围。
2. 在 `sources.json` 登记来源及其实际许可，不能仅因为网上公开就推定可开放再分发。
3. 为每个名称和别名保存准确 URL、日期与字段证据。
4. 排除不可靠同义词，检查是否与已有概念重复。
5. 在允许再分发且与项目许可兼容的前提下提交。外部来源不因代码为 MIT 或本数据集为 CC0 而自动改换许可。
6. 将来新增图标时独立记录作者、原始 URL、许可和署名要求。当前没有导入图标。
