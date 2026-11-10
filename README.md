# Chinese Ingredient API · 中国食材 API

面向中国菜谱的开放食材数据与只读 API。先把名称、别名、稳定 ID 和来源做好，再逐步扩展覆盖与图标。

**阶段：可运行的早期种子项目，不是完整食材百科。** 首版收录 18 条人工核验食材、4 个分类，不含调味品、营养数值、烹饪安全建议或图片。种子规模、来源及核验边界见 [数据来源](docs/DATA_SOURCES.md)。

## 立即运行

需要 Python 3.10+。运行与测试不需要安装任何第三方 Python 包。

```sh
git clone https://github.com/Dylan-Nihilo/chinese-ingredients-api.git
cd chinese-ingredients-api
```

```sh
python scripts/validate_data.py
python -m unittest discover -s tests -v
python -m ingredient_api
```

打开 http://127.0.0.1:8000/docs 。默认只监听本机，不会连接远程服务器、抓取新数据或发布任何内容。

```sh
curl --get 'http://127.0.0.1:8000/v1/ingredients' --data-urlencode 'q=番茄'
curl 'http://127.0.0.1:8000/v1/ingredients?limit=10&offset=0'
curl 'http://127.0.0.1:8000/v1/categories'
curl 'http://127.0.0.1:8000/v1/meta'
python examples/client.py 番茄
```

也可以指定端口：`python -m ingredient_api --port 8080`。显式指定 `--host 0.0.0.0` 才会对外监听，请勿直接暴露这个开发服务器到公网。

## 数据和 API 是同一份事实

- `data/ingredients.json` 是食材的唯一手工维护源；`data/categories.json` 和 `data/sources.json` 分别保存分类与来源目录。
- API 启动时校验并载入一个固定快照。离线导出与查询读取同一快照，不存在独立数据库的二次维护。修改文件后需重启服务。
- ID 如 `ing_000001` 为不含名称和分类含义的稳定标识。重命名不换 ID，不复用已分配 ID，不按名称重新编号。
- 搜索覆盖规范名及显式列出的中文别名，使用 Unicode NFKC、去除首尾空白及大小写规范化。繁体/方言仅在有来源且明确收录时支持，不自动推断。
- 精确规范名 > 精确别名 > 规范名前缀 > 别名前缀 > 规范名包含 > 别名包含，同级按 ID 排序。无搜索按 ID 排序。
- `sourceRefs` 标明来源支持哪些字段。分类属于项目编辑决策；不要把项目分类写成外部机构认可的分类。

```sh
python scripts/export_data.py --output dist
```

会导出 JSON、UTF-8 CSV 和 SHA-256 清单。JSON 逐字节保留源文件；CSV 的嵌套字段保留为 JSON 字符串，支持无损重建食材记录。CSV 不包含数据集级元信息，分发时需附上 `sources.json`、`categories.json`、`manifest.json` 和许可文件。

## API v1

| 方法 | 路径 | 内容 |
| --- | --- | --- |
| GET / HEAD | `/healthz` | 健康状态与版本 |
| GET / HEAD | `/v1/ingredients` | 搜索、分类筛选、分页 |
| GET / HEAD | `/v1/ingredients/{id}` | 稳定 ID 查询 |
| GET / HEAD | `/v1/categories` | 分类目录 |
| GET / HEAD | `/v1/sources` | 来源与许可证 |
| GET / HEAD | `/v1/meta` | 数据版本、覆盖数量、SHA-256 |
| GET / HEAD | `/v1/exports/ingredients.json` | 原始食材 JSON |
| GET / HEAD | `/v1/exports/ingredients.csv` | 无损食材 CSV |
| GET / HEAD | `/v1/exports/categories.json` | 原始分类 JSON |
| GET / HEAD | `/v1/exports/sources.json` | 原始来源 JSON |
| GET / HEAD | `/openapi.json` | OpenAPI 3.1 规范 |
| GET / HEAD | `/docs` | 无外部依赖的接口文档 |

列表参数：`q`（至多 120 字符）、`category`（分类 ID）、`limit`（1–100，默认 20）、`offset`（0–1000000，默认 0）。返回 `data` 与 `meta`，包含 `total`、`nextOffset`、`datasetVersion`。越界分页返回空列表；未知/重复参数与非法值返回 400，未知 ID/路由返回 404，写方法返回 405。OPTIONS 返回 Allow，不开启跨域访问。

所有成功 GET/HEAD 支持 ETag / If-None-Match（304）。`Cache-Control: no-cache` 要求客户端重验证；`X-Dataset-Version` 帮助识别快照。离线文件校验和包含在 `/v1/meta`。没有账户、鉴权、写接口、遥测或运行时上游请求。

## 目录

```text
data/             人工维护种子、分类和来源
ingredient_api/   Python 标准库 API 和强校验
schemas/          JSON Schema 2020-12
openapi.json      OpenAPI 3.1
scripts/          校验与确定性导出
examples/         最小客户端
tests/            数据、查询、真实 HTTP 与导出回归测试
docs/             数据边界、版本策略、扩展与贡献说明
```

## 许可证

代码：[MIT](LICENSE)。项目数据：[CC0 1.0](LICENSE-DATA)，来源和许可说明：[NOTICE.md](NOTICE.md)。数据中的引用链接用于溯源，不代表相关网站的文字、图片或品牌被项目重新授权。**当前没有图标资产**，未来图标将单独确认权利并明确许可。

## 贡献与下一步

见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [设计说明](docs/DESIGN.md)。先扩充有出处、可再分发的名称/别名；处理地区同名异物和加工形态；再设计调味品数据和原创图标。

本服务使用 Python 标准库 HTTP 服务器，适合本地开发、评审与离线集成。生产上线前应替换/封装为受维护的生产 HTTP 服务，补充 TLS、反向代理、流量限制、部署监控及安全评审。Docker/CI 配置是便利用例，不等于已完成生产部署或远程 CI 验证。
