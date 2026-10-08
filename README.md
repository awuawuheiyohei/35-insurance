# 少儿险条款事实对照

> 少儿意外险 + 百万医疗的**条款客观并排对比**工具。
> 每个字段可溯源至保险公司官网披露的条款原文。**不做评分、不做排名、不做推荐、不提供投保入口。**

---

## 为什么是这个定位

市面上的少儿险平台在解决「卖什么」，这个项目解决「看清楚」。
真正卡住一个家长的是三件事，而这三件事都不是"多列几个产品"能解决的：

1. **条款细节看不见** —— 销售给的是话术和产品名，不是条款里的保证续保期、免赔额、社保外用药范围
2. **不知道该配多少** —— 网上都在讲哪款好，没人告诉你孩子第一年该配哪两类、总预算多少
3. **数据会过期** —— 少儿险每年迭代数轮，过期数据比没有数据更危险

所以设计上有三条硬规则：

| 规则 | 实现方式 |
|---|---|
| 只做事实并排，不做优劣判断 | JSON Schema `additionalProperties: false`，**根本无法表达** `score`/`rank`/`recommended` 字段 |
| 每个数值必须能点回原文 | `source.fieldTrace` 强制要求：路径 + 页码 + 原文片段，缺一个字段校验就失败 |
| 数据陈旧必须可见 | `verifiedAt` + 文档 `sha256`，超 60 天标黄、超 180 天标红 |

---

## 合规边界（重要）

这是一个对外发布的产品，**合规不是文档里的建议，是代码里的约束**。

依据《保险销售行为管理办法》（金融监管总局令 2023 年第 2 号，2024-03-01 施行）第三条、
第十七条，及《互联网保险业务监管办法》第七条，本项目严格限定为
**条款信息披露聚合**，不构成保险销售行为。

完整红线清单、渠道资质矩阵、发布前自审清单见 **[`docs/01-合规边界.md`](docs/01-合规边界.md)**。

一句话版：**可以讲清"这份条款写了什么"，不可以讲清"你应该买哪份"。**

---

## 目录结构

```
insurance/
├── docs/
│   ├── 01-合规边界.md          # 法条引用 + 红线清单 + 渠道资质矩阵 + 自审清单
│   └── 02-数据源与溯源规范.md   # 数据源分层、溯源模型、陈旧性治理、导入流程
├── schema/product.schema.json  # 产品数据唯一 schema（同时承担合规约束）
├── data/
│   ├── _template/              # 填写模板
│   └── products/               # 真实产品数据（每条必须带官方出处）
├── src/insurance/
│   ├── trace.py                # 溯源交叉校验 + 保鲜度（schema 做不到的部分）
│   ├── compliance.py           # 禁用词 lint
│   ├── validate.py             # 校验 CLI
│   └── build.py                # 校验 → 聚合 → 产出给前端
├── web/                        # PWA 前端（零构建，原生 JS）
├── scripts/demo_data.py        # 生成虚构演示数据，用于本地预览
└── tests/                      # 28 项行为测试，全部使用虚构 fixture
```

---

## 怎么跑

```bash
python3 -m venv .venv && .venv/bin/pip install jsonschema

# 校验数据（校验不通过就不允许进库）
PYTHONPATH=src .venv/bin/python -m insurance.validate --lint

# 跑测试
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests

# 构建前端数据
PYTHONPATH=src .venv/bin/python -m insurance.build

# 本地预览
python3 -m http.server -d web 8000   # 打开 http://localhost:8000
```

### 想先看看长什么样

正式库是空的（见下节），但可以用**虚构数据**预览完整渲染效果：

```bash
PYTHONPATH=src .venv/bin/python scripts/demo_data.py      # 生成 3 个【示例·虚构】产品
PYTHONPATH=src .venv/bin/python -m insurance.build
python3 -m http.server -d web 8000

PYTHONPATH=src .venv/bin/python scripts/demo_data.py --clean   # 用完清掉
```

演示数据覆盖了停售标记、数据过期标记、以及「本产品没有某项责任」这类 null 断言
——后者同样强制要求溯源。**演示数据永远不进正式库。**

---

## 导入一个产品的流程

```
保险公司官网「公开信息披露」栏目
        ↓  下载条款 PDF + 费率表 PDF（记下 sha256）
   人工阅读条款原文，逐字段填写 + 抄录 quote + 记页码
        ↓
   data/products/<id>.json
        ↓
   python -m insurance.validate   ← 不通过就回上一步
```

**不允许**先填数据、来源以后补。校验器会把缺失溯源的字段逐条列出来。

详细步骤见 [`docs/02-数据源与溯源规范.md`](docs/02-数据源与溯源规范.md) §5。

---

## 现状与路线图

- [x] 合规边界文档（法条核实到条文级）
- [x] 数据 schema + 溯源校验器 + 合规 lint + 28 项测试
- [x] PWA 前端骨架（字段溯源弹层、保鲜度标记、无排序）
- [x] 虚构演示数据脚本（用于走查渲染效果）
- [ ] **导入首批产品数据（20-30 款，当前最大的空缺）**
- [ ] ICP 备案后上线
- [ ] 律师复核
- [ ] 重疾险 / 教育金（第二期）

---

## 数据空缺的说明

`data/products/` 目前是**空的**，这是刻意的。

本项目不会填入任何未经官方条款核对的数据 —— 空库比错数据安全，
这与"人命关天、拒绝编造"的原则一致。首批数据的导入是下一步的主要工作量。