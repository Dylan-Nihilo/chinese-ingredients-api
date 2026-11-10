# 贡献食材

谢谢你一起维护适合中国菜谱的食材基础数据。

## 当前范围

只收食材；暂不收盐、糖、油、酱料、香辛料及其他调味品。不在这一版强行判定姜、蒜等兼具主料与调味用途的边界。肉类部位、加工形态、品种、物种和上位概念不能因为相近而当成同义词。

## 每条记录的要求

1. 检查现有 ID、规范名和别名，避免重复建条目。新 ID 使用当前最大已登记/预留数字 + 1（首版 1–64 已登记或预留，下一编号从 65 开始）；一旦发行不可复用或按字母排序重新编号。并行贡献冲突在合并前解决。
2. 中文规范名要常见、具体、可核验。别名记录 locale，并提供直接支持其同义关系的来源。没有把握就不加。
3. 用当前分类目录；分类由项目编辑，不能声称是来源机构认可的分类。
4. 只引入许可允许再分发的结构化数据、原创事实编排或已取得必要许可的内容。不要复制百科描述、食品包装图或搜索结果图片。
5. `sourceRefs` 必须列出 HTTPS 来源、核验日期、支持的字段以及核验备注；不同来源支持不同字段时分开引用。新增来源须更新 `sources.json` 并说明许可。
6. 本版 `description`、`icon` 保持 null。来源许可只覆盖自己的内容，不覆盖来源页面链接的其他作品。
7. 修改数据更新 `datasetVersion` 与 `releasedAt`，并在 CHANGELOG.md 记录。补数据不等于变更 API 主版本。

## 提交前运行

```sh
python scripts/validate_data.py
python -m unittest discover -s tests -v
python -m compileall -q ingredient_api scripts examples tests
python scripts/export_data.py --output dist
```

与旧版本对比：`python scripts/validate_data.py --baseline /path/to/previous/ingredients.json`。这个检查能发现删除 ID 或丢失旧名，不能代替人审食材身份、来源内容或许可。

数据贡献默认采用项目 CC0，代码贡献采用 MIT。只能贡献自己有权授权的内容；引用并不自动解决权利问题。纠正条目身份、合并 ID、删除记录或改变 API 语义前先讨论迁移方案。
