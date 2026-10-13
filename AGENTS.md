# AGENTS.md

少儿意外险 + 百万医疗的**条款客观并排对比**工具，计划对外发布。

一句话定性：**只做条款事实对比，不做产品优劣判断。**分界线是——本项目会不会引导
用户形成「买这个」的决定，以及我们是否从中获利。

本仓库在 `mass/` 下带编号前缀（如 `35-insurance`），编号会变，不要在代码或文档里
硬编码绝对路径。仓库根路径一律用 `Path(__file__).resolve().parents[N]` 推导。

---

## 改代码前先读

| 文档 | 什么时候看 |
|---|---|
| [`docs/01-合规边界.md`](docs/01-合规边界.md) | 碰 schema、前端文案、命名之前。法条引用到条文级，含红线清单、渠道资质矩阵、发布前自审清单 |
| [`docs/02-数据源与溯源规范.md`](docs/02-数据源与溯源规范.md) | 加产品或基准数据之前。数据源四层分级、`fieldTrace` 模型、陈旧性治理、导入流程 |

这两份是约束，不是背景资料。

---

## 三条红线（不可绕过）

### 1. 每个数值必须能点回官方原文

产品字段要有 `source.fieldTrace`（路径 + 页码 + 原文片段），基准样本要有
`source.premiumQuote`（费率表原文）。缺了校验器会硬失败。

- **不允许**先填数据、来源以后补
- **不允许**从第三方测评文章抄数字
- **不允许**让 LLM 生成任何数值字段——本库刻意不引入 LLM 依赖

### 2. 空的数据目录是刻意的

`data/products/` 和 `data/benchmarks/` 长期为空，这是设计不是遗漏。
**空库比错数据安全。**

要预览渲染效果用虚构数据脚本，用完必须清理：

```bash
PYTHONPATH=src .venv/bin/python scripts/demo_data.py       # 产品演示
PYTHONPATH=src .venv/bin/python scripts/demo_benchmarks.py # 基准演示
PYTHONPATH=src .venv/bin/python scripts/demo_data.py --clean
```

演示数据全部带「虚构」标识与 `example.com` URL，绝不能进正式库。

### 3. 不做优劣判断

由两层强制，不靠自觉：

- **schema 层**：两套 schema 都是 `additionalProperties: false`，
  `score` / `rank` / `recommended` / `purchaseUrl` **在类型层面无法表达**。
  这是合规约束，**不是可以为了方便而放宽的严格校验**。
- **文案层**：`insurance.validate --lint` 扫描 `web/` 与 `data/`，命中 21 个
  禁用词（推荐/最佳/排名/评分/即将下架…）即失败。否定式说明（如「本页不提供
  排序、评分功能」）需在行内加 `lint:ignore` 标记。

---

## 脱敏约定

本项目计划对外发布，仓库将来可能进公开 GitHub。文档、commit message、演示数据里
不要留下能定位到具体家庭的信息。

**判定标准**：出生年月 + 性别 + 保额 + 年交保费凑齐，基本已可定位到具体保单。
投保人信息（出生年月、性别、已投保事实、渠道与业务员）一律不入库；产品参数
（保额、缴费期、费率表保费）可以留，因为那是公开费率表的数字，谁都能查到。

- ✗ `2026-07 出生的孩子，女宝，已投保，年交 11,555.11 元`
- ✓ `新华健康多倍保庆典版 · 0 岁女 · 50 万保额 · 终身 20 年缴 · 年交 11,555.11 元`

两条容易踩的：

- **个人成交价 ≠ 费率表价**。线下渠道可能给额外优惠，两者数字不同。入库的必须是
  费率表数字；真实成交价留在个人笔记里，不要写进仓库任何文件。
- **演示数据一律虚构**。`example.com` 与「虚构」标识是红线 2 的一部分，不要为了
  「真实感」把虚构数据替换成真实公司名或真实产品名。

清除已经泄漏的内容，事后改文件不够——已推送的 commit 仍能被翻出来，需要
`git filter-repo` 或直接重开仓库。所以**原则上一开始就不要写**。

---

## 命令

```bash
# 校验（--lint 附带合规文案扫描）
PYTHONPATH=src .venv/bin/python -m insurance.validate --lint

# 测试
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests

# 构建前端数据（校验不通过则拒绝产出）
PYTHONPATH=src .venv/bin/python -m insurance.build

# 保费基准查询
PYTHONPATH=src .venv/bin/python -m insurance.benchmark \
    --age 0 --gender female --sum-insured 500000 --term lifetime --pay 30 --type consumption

# 本地预览
python3 -m http.server 8765 -d web    # 不要用 5060/5061，Chrome 黑名单端口
```

---

## 当前待办

- [ ] **导入首批真实数据**：`data/products/`（意外险 + 百万医疗，20-30 款）与
      `data/benchmarks/`（每组 ≥3 样本）。这是当前最大的空缺。
- [ ] 律师复核合规定性（`docs/01-合规边界.md` §7）
- [ ] ICP 备案后上线
- [ ] 第二期：重疾险 / 教育金

### 已知待接入的数据

用户已决定为 2026-07 出生的孩子投保**新华健康多倍保庆典版重大疾病保险**（销售上门，
0 岁女宝 50 万保额终身 20 年缴，年交 11,555.11 元）。

拿到该单的**费率表 + 现金价值表 PDF** 后，作为一条 `productType: "savings"` 的样本
写入 `data/benchmarks/`，把「同样 50 万保额，储蓄型是消费型的 5 倍」这个坑固化进工具。
不要写进 `data/products/`——v1 范围只有意外险和百万医疗。

---

## 不要做

- 不要放宽 `additionalProperties: false` 来「方便加字段」，新字段要先想清楚它是否
  触及红线（红线 3）
- 不要往 `data/` 放演示数据或未核对数据
- 不要为了简化而删改 `docs/01` 里的法条引用
- 不要引入 LLM 依赖或让模型生成数值
- 不要提供任何投保 / 报价 / 核保外链