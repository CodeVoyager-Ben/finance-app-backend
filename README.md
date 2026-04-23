# 个人财务管理系统 (Finance App)

全栈个人财务管理应用，后端 Django + DRF，前端 React + Vite + Ant Design。支持收支记账、投资管理、借贷管理、报表分析等功能。

---

## 目录

- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [功能概览](#功能概览)
- [后端 API 文档](#后端-api-文档)
- [数据模型](#数据模型)
- [前端页面说明](#前端页面说明)
- [默认数据](#默认数据)
- [管理命令](#管理命令)

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | Django + DRF | 5.2 / 3.15+ |
| 数据库 | MySQL | 8.x |
| 认证 | SimpleJWT | 5.3+ |
| API文档 | drf-spectacular | 0.27+ |
| 其他后端依赖 | django-cors-headers, django-filter, openpyxl, Pillow, akshare, APScheduler | - |
| 前端框架 | React | 18.3 |
| 构建工具 | Vite | 6.0 |
| UI组件库 | Ant Design | 5.22 |
| 图表 | ECharts | 5.5 |
| 状态管理 | Zustand | 5.0 |
| HTTP客户端 | Axios | 1.7 |
| 路由 | React Router DOM | 6.28 |
| 语言 | Python 3.13 / JavaScript (JSX) | - |

---

## 项目结构

```
finance_app/
├── backend/                    # Django 后端
│   ├── config/                 # 项目配置
│   │   ├── settings.py         # Django 设置（MySQL、JWT、CORS、DRF）
│   │   ├── urls.py             # 根路由
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── users/              # 用户模块（注册、登录、JWT）
│   │   ├── transactions/       # 收支模块（账户、分类、流水、预算）
│   │   ├── investments/        # 投资模块（资产类型、多币种、持仓、交易、分红、汇率、自动行情）
│   │   ├── lending/            # 借贷模块（借贷记录、还款）
│   │   └── reports/            # 报表模块（资产负债、导出）
│   ├── utils/                  # 工具（空）
│   ├── venv/                   # Python 虚拟环境
│   ├── manage.py
│   └── requirements.txt
│
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── api/                # API 调用层
│   │   │   ├── request.js      # Axios 实例（拦截器、401处理）
│   │   │   ├── auth.js         # 认证 API（5个函数）
│   │   │   └── finance.js      # 业务 API（55+个函数）
│   │   ├── store/
│   │   │   └── authStore.js    # Zustand 认证状态
│   │   ├── components/
│   │   │   └── MainLayout.jsx  # 主布局（侧边栏、头部、首次账户引导）
│   │   ├── pages/
│   │   │   ├── Login.jsx       # 登录/注册页
│   │   │   ├── Dashboard/      # 仪表盘
│   │   │   ├── Transactions/   # 收支记账
│   │   │   ├── Calendar/       # 日历视图
│   │   │   ├── Investments/    # 投资管理（5 Tab：概览/持仓/交易/分红/分析，11子组件）
│   │   │   ├── Lending/        # 借贷管理
│   │   │   ├── Reports/        # 报表中心（4个子组件）
│   │   │   └── Settings/       # 个人设置
│   │   ├── styles/global.css
│   │   ├── App.jsx             # 路由配置
│   │   └── main.jsx            # 入口（Ant Design 中文主题）
│   ├── index.html
│   ├── vite.config.js          # Vite 配置（端口3000，API代理到8000）
│   └── package.json
│
└── README.md                   # 本文件
```

---

## 快速开始

### 环境要求

- Python 3.13+
- Node.js 18+
- MySQL 8.x（数据库名 `finance_app`，字符集 `utf8mb4`）

### 1. 数据库

```sql
CREATE DATABASE finance_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

数据库配置在 `backend/config/settings.py`：

```
HOST: 127.0.0.1
PORT: 3306
USER: root
PASSWORD: root
NAME: finance_app
```

### 2. 后端

```bash
cd finance_app/backend
python -m venv venv
source venv/bin/activate          # macOS/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```

### 3. 前端

```bash
cd finance_app/frontend
npm install
npm run dev                       # 启动在 http://localhost:3000
```

### 4. 访问

| 地址 | 说明 |
|------|------|
| http://localhost:3000 | 前端应用 |
| http://localhost:8000/api/docs/ | Swagger API 文档 |
| http://localhost:8000/admin/ | Django 后台管理 |

### 5. 初始化分类数据（可选）

注册用户时会自动创建默认分类和账户。如需为已有用户补充分类：

```bash
cd backend
source venv/bin/activate
python manage.py init_categories                  # 所有用户
python manage.py init_categories --username admin  # 指定用户
```

---

## 功能概览

### 六大功能模块

| 模块 | 路由 | 核心功能 |
|------|------|----------|
| 仪表盘 | `/` | 月度收支总览、预算进度、支出分类饼图、月度趋势图、最近交易 |
| 收支记账 | `/transactions` | 四种类型（支出/收入/转账/还信用卡）、数字键盘快速记账、分类选择 |
| 日历视图 | `/calendar` | 按日查看收支、月度汇总、点击日期查看交易明细 |
| 投资管理 | `/investments` | 多资产类型、多币种、持仓盈亏、分红利息、资产配置、年化收益 |
| 借贷管理 | `/lending` | 借出/借入记录、还款录入、核销、状态跟踪 |
| 报表中心 | `/reports` | 资产负债表、净资产趋势、资产配置、财务健康指标、Excel导出 |

### 其他功能

| 功能 | 说明 |
|------|------|
| 用户注册/登录 | 用户名+密码注册，密码强度检测，JWT认证 |
| 个人设置 | 修改个人信息、管理账户/分类/预算 |
| 首次引导 | 首次登录自动弹窗，一键创建默认账户 |
| 数据隔离 | 所有数据按用户隔离，JWT鉴权 |

---

## 后端 API 文档

### 认证相关 `api/auth/`

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/auth/register/` | POST | 公开 | 注册（自动创建默认分类+账户） |
| `/api/auth/login/` | POST | 公开 | 登录，返回 access + refresh token |
| `/api/auth/refresh/` | POST | 公开 | 刷新 access token |
| `/api/auth/profile/` | GET/PATCH | 认证 | 查看/修改个人信息 |
| `/api/auth/change-password/` | PUT | 认证 | 修改密码 |

**JWT 配置：** access 1天过期，refresh 7天过期，自动轮换。

### 账户 `api/accounts/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/accounts/` | GET | 账户列表 |
| `/api/accounts/` | POST | 创建账户 |
| `/api/accounts/{id}/` | GET/PATCH/DELETE | 读写删单个账户 |

**账户类型：** cash（现金）、bank（银行卡）、credit_card（信用卡）、alipay（支付宝）、wechat（微信）、other（其他）

### 分类 `api/categories/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/categories/` | GET | 分类列表（支持 `?category_type=expense/income`，只返回顶级分类，嵌套children） |
| `/api/categories/` | POST | 创建分类 |
| `/api/categories/{id}/` | GET/PATCH/DELETE | 读写删 |

### 收支流水 `api/transactions/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/transactions/` | GET | 流水列表（支持筛选、搜索、排序、分页） |
| `/api/transactions/` | POST | 创建流水（自动更新账户余额） |
| `/api/transactions/{id}/` | PATCH/DELETE | 修改/删除（自动回滚再重算余额） |
| `/api/transactions/daily_summary/` | GET | 按日汇总（参数: year, month） |
| `/api/transactions/monthly_summary/` | GET | 按月汇总（参数: year） |
| `/api/transactions/category_summary/` | GET | 按分类汇总（参数: transaction_type, start_date, end_date, year, month） |
| `/api/transactions/dashboard/` | GET | 仪表盘数据（本月收支、今日收支、账户总额、最近10笔、预算） |

**流水类型：** income（收入）、expense（支出）、transfer（转账/还信用卡）

**筛选参数：** `account`, `category`, `transaction_type`, `date`, `start_date`, `end_date`
**搜索：** `search`（模糊匹配 note 和分类名称）
**排序：** `ordering`（date, amount, created_at，加 `-` 倒序）
**分页：** 默认每页 20 条

**余额变动规则：**
- income → 账户余额 +amount
- expense → 账户余额 -amount
- transfer → 源账户 -amount，目标账户(to_account) +amount

### 预算 `api/budgets/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/budgets/` | GET | 预算列表（含已花费/剩余/百分比，自动计算） |
| `/api/budgets/` | POST | 创建预算（自动填入当前年月） |
| `/api/budgets/{id}/` | PATCH/DELETE | 修改/删除 |

**周期：** monthly（月度）、yearly（年度）。category 为空时代表总预算。

### 资产类型 `api/asset-types/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/asset-types/` | GET | 资产类型列表（系统预设 + 用户自定义） |
| `/api/asset-types/` | POST | 创建自定义资产类型 |
| `/api/asset-types/{id}/` | PATCH/DELETE | 修改/删除（系统预设不可改） |

**系统预设（9种）：** 股票、基金、债券、黄金、房产、定期存款、保险、虚拟货币、期货
**大类分组：** 证券类(security)、商品类(commodity)、固收类(fixed_income)、房产类(real_estate)、保险类(insurance)、其他(other)

### 汇率 `api/exchange-rates/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/exchange-rates/` | GET/POST | 汇率列表/新增 |
| `/api/exchange-rates/latest/` | GET | 各币种最新汇率 |
| `/api/exchange-rates/{id}/` | DELETE | 删除汇率 |

**支持币种：** CNY、USD、HKD、EUR、GBP、JPY、AUD、CAD、SGD

### 投资 `api/investments/` + `api/holdings/` + `api/invest-trans/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/investments/` | GET/POST | 投资账户 CRUD（含 asset_type、currency） |
| `/api/investments/{id}/summary/` | GET | 单账户汇总（持仓/市值/盈亏/分红，原币+CNY） |
| `/api/holdings/` | GET/POST | 持仓列表（含日盈亏/年化收益/持有天数等计算属性） |
| `/api/holdings/{id}/` | PATCH | 更新价格/昨收价/分组标签 |
| `/api/holdings/dashboard/` | GET | 投资概览（总市值/总成本/总盈亏/日盈亏/累计分红/按类型分组/按币种分组） |
| `/api/holdings/batch_update_prices/` | POST | 批量更新持仓价格（自动设置昨收价） |
| `/api/holdings/auto-update-prices/` | POST | 自动获取A股最新价格（东方财富API），保存每日快照 |
| `/api/holdings/daily-snapshots/` | GET | 每日持仓快照查询（支持日期范围筛选） |
| `/api/invest-trans/` | GET/POST | 交易记录（支持9种交易类型，自动计算手续费和盈亏） |

**交易类型：** buy（买入）、sell（卖出）、dividend（分红）、interest（利息）、dividend_reinvest（分红再投资）、deposit（入金）、withdraw（出金）、fee（费用）、split（拆股/合股）

### 分红记录 `api/dividend-records/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/dividend-records/` | GET/POST | 分红/利息记录 CRUD |
| `/api/dividend-records/{id}/` | PATCH/DELETE | 修改/删除 |

**分红方式：** cash（现金分红）、reinvest（分红再投资）、interest（利息收入）
**自动处理：** 创建分红记录时自动生成关联交易，更新持仓成本和累计分红，再投资自动建仓

### 借贷 `api/lending-records/` + `api/repayments/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/lending-records/` | GET/POST | 借贷记录 CRUD |
| `/api/lending-records/summary/` | GET | 汇总（总借出/总借入/待收回/待归还/利息） |
| `/api/repayments/` | GET/POST | 还款记录（自动更新父记录的已还金额和状态） |

**记录类型：** lend（借出）、borrow（借入）
**状态流转：** outstanding（未还清）→ partial（部分归还）→ settled（已结清）或 written_off（已核销）
**还款类型：** collect（收款）、repay（还款）

### 报表 `api/reports/`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/reports/balance-sheet/?date=YYYY-MM-DD` | GET | 资产负债表（支持历史日期） |
| `/api/reports/net-worth-history/?months=12` | GET | 净资产历史趋势 |
| `/api/reports/export/?type=transactions&start_date=&end_date=` | GET | 导出Excel（收支明细 / 资产负债表） |

**资产负债表返回：** 现金资产列表、投资持仓、资产配置、负债列表、净资产、财务健康指标（资产负债率、流动性比率、储蓄率、投资比率、健康等级）、环比变化。

---

## 数据模型

### 模型关系图

```
User
 ├── 1:N ── Account ──────────────┐
 │    (cash/bank/credit_card/      │
 │     alipay/wechat/other)        │
 │                                 │
 ├── 1:N ── Category (自引用树)    │
 │    (income/expense)             │
 │                                 │
 ├── 1:N ── Transaction ───────────┤── Account (FK: account, to_account)
 │    (income/expense/transfer)    │     (FK: category)
 │                                 │
 ├── 1:N ── Budget                │
 │    (monthly/yearly)             │
 │                                 │
 ├── 1:N ── InvestmentAccount     │── AssetType (FK: asset_type)
 │    (多币种 CNY/USD/HKD/...)     │
 │    ├── 1:N ── InvestmentHolding │ (含日盈亏/年化收益/持有天数/累计分红)
 │    ├── 1:N ── InvestmentTransaction (9种交易类型)
 │    └── 1:N ── DividendRecord   │ (现金分红/再投资/利息)
 │                                 │
 ├── AssetType (系统预设+自定义)    │
 │                                 │
 └── 1:N ── LendingRecord ────────┘── Account (FK: account, nullable)
      (lend/borrow)                     └── 1:N ── Repayment (collect/repay)
```

### 各模型字段一览

#### User（自定义用户，继承 AbstractUser）

| 字段 | 类型 | 说明 |
|------|------|------|
| username | CharField | 用户名 |
| email | EmailField | 邮箱 |
| password | CharField | 密码（加密存储） |
| phone | CharField(20) | 手机号，可空 |
| avatar | ImageField | 头像，上传到 avatars/ |
| currency | CharField(10) | 币种，默认 CNY |

#### Account（资金账户）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK → User | 所属用户 |
| name | CharField(50) | 账户名称 |
| account_type | CharField(20) | cash/bank/credit_card/alipay/wechat/other |
| balance | Decimal(15,2) | 余额 |
| icon | CharField(50) | 图标emoji |
| color | CharField(20) | 主题色 |
| is_active | Boolean | 是否启用 |

#### Category（收支分类，二级树形结构）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK → User | 所属用户 |
| name | CharField(50) | 分类名称 |
| category_type | CharField(10) | income/expense |
| icon | CharField(50) | 图标emoji |
| color | CharField(20) | 主题色 |
| parent | FK → self | 父分类（空=顶级） |
| sort_order | Integer | 排序序号 |
| is_active | Boolean | 是否启用 |

#### Transaction（收支流水）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK → User | 所属用户 |
| account | FK → Account | 资金账户（源账户） |
| to_account | FK → Account | 目标账户（仅转账/还信用卡时使用） |
| category | FK → Category | 分类（可空） |
| transaction_type | CharField(10) | income/expense/transfer |
| amount | Decimal(15,2) | 金额，必须 > 0 |
| note | CharField(200) | 备注 |
| date | DateField | 日期 |

#### Budget（预算）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK → User | 所属用户 |
| category | FK → Category | 分类（空=总预算） |
| amount | Decimal(15,2) | 预算金额 |
| period | CharField(10) | monthly/yearly |
| year | Integer | 年份 |
| month | Integer | 月份 |

#### AssetType（资产类型）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK → User (nullable) | 所属用户（null=系统预设） |
| code | CharField(30) | 类型编码 |
| name | CharField(30) | 类型名称 |
| category | CharField(20) | 大类(security/commodity/fixed_income/real_estate/insurance/other) |
| icon | CharField(10) | 图标 |
| color | CharField(7) | 颜色 |
| is_active | Boolean | 是否启用 |
| sort_order | Integer | 排序 |

#### ExchangeRate（汇率）

| 字段 | 类型 | 说明 |
|------|------|------|
| base_currency | CharField(3) | 基准货币（默认CNY） |
| target_currency | CharField(3) | 目标货币 |
| rate | Decimal(12,6) | 汇率（1目标货币 = ? CNY） |
| rate_date | DateField | 汇率日期 |
| source | CharField(30) | 来源（manual/api） |

#### InvestmentAccount（投资账户）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK → User | 所属用户 |
| name | CharField(50) | 账户名称 |
| broker | CharField(50) | 券商/平台 |
| asset_type | FK → AssetType | 资产类型 |
| currency | CharField(3) | 币种（ISO 4217，默认CNY） |
| balance | Decimal(15,2) | 账户余额 |
| is_active | Boolean | 是否启用 |

#### InvestmentHolding（投资持仓）

| 字段 | 类型 | 说明 |
|------|------|------|
| investment_account | FK → InvestmentAccount | 所属投资账户 |
| symbol | CharField(30) | 代码 |
| name | CharField(50) | 名称 |
| quantity | Decimal(15,4) | 持有数量 |
| avg_cost | Decimal(15,4) | 平均成本 |
| current_price | Decimal(15,4) | 当前价格 |
| first_buy_date | DateField | 首次买入日期 |
| previous_close_price | Decimal(15,4) | 昨收价（用于日盈亏） |
| accumulated_dividend | Decimal(15,2) | 累计分红/利息 |
| group_tag | CharField(50) | 自定义分组标签 |
| currency | CharField(3) | 币种（空=继承账户） |

**计算属性：** market_value（市值）、cost_value（成本）、profit_loss（盈亏）、profit_loss_pct（盈亏比例）、holding_days（持有天数）、daily_profit_loss（日盈亏）、daily_profit_loss_pct（日盈亏%）、total_return_rate（总回报率，含分红）、annualized_return（年化收益率）、daily_avg_cost（日均成本）、effective_currency（实际币种）

#### InvestmentTransaction（投资交易）

| 字段 | 类型 | 说明 |
|------|------|------|
| investment_account | FK → InvestmentAccount | 投资账户 |
| holding | FK → InvestmentHolding | 关联持仓 |
| symbol | CharField(30) | 代码 |
| name | CharField(50) | 名称 |
| transaction_type | CharField(20) | buy/sell/dividend/interest/dividend_reinvest/deposit/withdraw/fee/split |
| quantity | Decimal(15,4) | 数量 |
| price | Decimal(15,4) | 价格 |
| amount | Decimal(15,2) | 交易金额 |
| fee | Decimal(10,2) | 手续费 |
| profit_loss | Decimal(15,2) | 盈亏 |
| dividend_per_unit | Decimal(10,4) | 每单位分红 |
| related_transaction | FK → self | 分红再投资关联 |
| date | DateField | 日期 |
| note | CharField(200) | 备注 |

#### DividendRecord（分红/利息记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| investment_account | FK → InvestmentAccount | 投资账户 |
| holding | FK → InvestmentHolding | 关联持仓 |
| symbol | CharField(30) | 代码 |
| name | CharField(50) | 名称 |
| dividend_type | CharField(10) | cash（现金分红）/reinvest（再投资）/interest（利息） |
| ex_date | DateField | 除权除息日 |
| pay_date | DateField | 发放日 |
| dividend_per_unit | Decimal(10,4) | 每单位分红 |
| quantity | Decimal(15,4) | 持有数量 |
| total_amount | Decimal(15,2) | 总金额 |
| tax | Decimal(10,2) | 扣税 |
| net_amount | Decimal(15,2) | 税后净额 |
| transaction | OneToOne → InvestmentTransaction | 关联交易记录 |

#### DailyHoldingSnapshot（每日持仓快照）

| 字段 | 类型 | 说明 |
|------|------|------|
| holding | FK → InvestmentHolding | 关联持仓 |
| user | FK → User | 所属用户 |
| symbol | CharField(30) | 代码 |
| name | CharField(50) | 名称 |
| date | DateField | 快照日期 |
| quantity | Decimal(15,4) | 持有数量 |
| avg_cost | Decimal(15,4) | 平均成本 |
| close_price | Decimal(15,4) | 收盘价 |
| previous_close | Decimal(15,4) | 昨收价 |
| market_value | Decimal(15,2) | 市值 |
| cost_value | Decimal(15,2) | 成本 |
| daily_pl | Decimal(15,2) | 当日盈亏 |
| total_pl | Decimal(15,2) | 累计盈亏 |
| daily_pl_pct | Decimal(8,4) | 当日盈亏% |
| total_pl_pct | Decimal(8,4) | 累计盈亏% |

**唯一约束：** `['holding', 'date']`，每个持仓每天只有一条快照。

#### LendingRecord（借贷记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK → User | 所属用户 |
| record_type | CharField(10) | lend（借出）/ borrow（借入） |
| counterparty | CharField(50) | 对方姓名 |
| amount | Decimal(15,2) | 金额 |
| repaid_amount | Decimal(15,2) | 已还金额 |
| interest_amount | Decimal(15,2) | 利息金额 |
| account | FK → Account | 关联账户（可空） |
| status | CharField(15) | outstanding/partial/settled/written_off |
| date | DateField | 日期 |
| expected_return_date | DateField | 预计归还日期 |

**计算属性：** remaining_amount（剩余金额 = amount - repaid_amount）

#### Repayment（还款记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| lending_record | FK → LendingRecord | 关联借贷记录 |
| repay_type | CharField(10) | collect（收款）/ repay（还款） |
| amount | Decimal(15,2) | 还款金额 |
| interest | Decimal(15,2) | 利息 |
| account | FK → Account | 关联账户 |
| date | DateField | 日期 |

---

## 前端页面说明

### 全局布局 (MainLayout)

- 左侧可折叠侧边栏，7个导航菜单
- 顶部用户头像下拉菜单（个人设置、退出登录）
- 首次登录检测：无账户时弹出引导弹窗，支持一键创建默认账户或自定义创建

### 登录/注册页 (Login)

**登录：** 用户名 + 密码，成功后存 JWT token 到 localStorage。

**注册：** 用户名 + 邮箱 + 手机(选填) + 密码 + 确认密码。密码强度实时检测（长度、大小写、数字、特殊字符），强度 < 40 不允许注册。注册成功后自动创建默认分类（12个支出大类+55个子类、4个收入大类+16个子类）和5个默认账户。

### 仪表盘 (Dashboard)

1. **4张统计卡片：** 本月收入（绿）、本月支出（红）、本月结余（蓝）、账户总余额（紫）
2. **预算进度卡片：** 每个预算分类一张卡片，显示已花/剩余/进度条，支持添加/编辑预算
3. **支出分类饼图：** ECharts 环形图，按分类展示当月支出占比
4. **月度趋势图：** 柱状图（收入绿柱/支出红柱）+ 折线图（结余蓝线），展示全年12个月数据
5. **最近交易表格：** 最近10笔交易，链接到收支记账页

### 收支记账 (Transactions)

1. **类型筛选：** Segmented 切换（全部/支出/收入/转账/还信用卡）
2. **交易列表：** 表格展示日期/分类/类型/账户/金额/备注/操作。转账显示"源账户 → 目标账户"。
3. **快速记账抽屉：**
   - 4个类型按钮（支出红/收入绿/转账蓝/还信用卡紫）
   - 分类选择网格（5列，emoji图标）
   - 转账/还信用卡显示目标账户选择器（还信用卡自动筛选信用卡账户）
   - 还信用卡固定分类为"💳 还信用卡"
   - 大号金额输入框（颜色跟随类型）
   - 4x4数字键盘（含删除/小数点/保存）
   - 账户选择、日期选择、备注输入

### 日历视图 (Calendar)

1. **月度汇总栏：** 月份导航、今日按钮、月收入/支出/结余
2. **日历网格：** 每格显示日期+收入+支出，背景色根据净收支深浅变化，今天高亮
3. **日期详情弹窗：** 点击某天弹出该日交易明细列表

### 投资管理 (Investments)

**5个Tab页面：**

1. **概览 Tab：**
   - 6张统计卡片：总市值/总成本/总盈亏（含百分比）/今日盈亏/累计分红/持仓数
   - 投资账户卡片（含币种标签、类型标签、余额、持仓市值）
   - 资产配置饼图（按资产类型展示占比）

2. **持仓 Tab：**
   - 增强持仓表格（14列）：代码/名称/类型/分组/数量/成本价/现价/市值/日盈亏/总盈亏/总回报率/年化收益/持有天数/币种
   - 持仓详情抽屉（完整指标 + 交易历史）

3. **交易 Tab：**
   - 交易记录表格，支持9种交易类型（买入/卖出/分红/利息/再投资/入金/出金/费用/拆股）

4. **分红 Tab：**
   - 分红/利息记录专用表格（除权日/类型/代码/每单位分红/数量/总金额/扣税/税后净额）
   - 记录分红弹窗（支持现金分红/分红再投资/利息收入）

5. **分析 Tab：**
   - 按资产类型分布表（市值/成本/盈亏/占比）
   - 按币种分布表（原币市值/人民币市值/汇率）

**新增功能：**
   - 9种资产类型（股票/基金/债券/黄金/房产/定期存款/保险/虚拟货币/期货）+ 用户自定义
   - 多币种支持（CNY/USD/HKD/EUR/GBP/JPY/AUD/CAD/SGD）+ 人民币自动汇总
   - 分红/利息记录（现金分红/再投资/利息收入）
   - 增强分析：日盈亏、年化收益、持有天数、日均成本、总回报率
   - 自动获取A股最新价格（东方财富行情API），一键更新所有持仓
   - 每日持仓快照（自动保存收盘数据，支持历史盈亏查看）
   - 卖出功能：持仓行内卖出按钮，支持数量校验、手续费预估、盈亏预览
   - 交易自动计算手续费（佣金万2.5最低5元、印花税0.05%、过户费0.001%）
   - 投资账户总资产展示（余额 + 持仓市值）
   - 手动/自动批量价格更新

### 借贷管理 (Lending)

1. **4张汇总卡片：** 总借出/总借入/待收回/待归还
2. **借出/借入 Tab 切换 + 状态筛选**（全部/未还清/部分归还/已结清/已核销）
3. **记录表格：** 对方/金额/已还/剩余/状态/日期/预计归还/事由/操作
4. **新增/编辑弹窗：** 类型/对方/金额/关联账户/日期/预计归还日期/事由/备注
5. **还款弹窗：** 显示汇总信息，录入还款类型/金额/利息/账户/日期
6. **详情抽屉：** 完整信息展示+还款历史表格，右上角编辑按钮（已结清/已核销时隐藏）

### 报表中心 (Reports)

1. **4张统计卡片：** 总资产/总负债/净资产/环比变化
2. **净资产趋势折线图：** 3条线（资产/负债/净资产），大额自动显示"万"单位
3. **资产配置饼图：** 按账户类型展示占比，中心显示总资产
4. **财务健康指标：** 资产负债率/流动性比率/月储蓄率/净资产环比，各带阈值颜色
5. **资产负债表明细：** 左侧现金+投资+负债表格，右侧汇总卡片
6. **Excel导出：** 支持日期范围筛选，可导出收支明细或资产负债表（.xlsx）

### 个人设置 (Settings)

4个Tab：

1. **个人信息：** 查看/修改邮箱、手机号
2. **账户管理：** 表格展示所有账户，支持新增/编辑/删除/启停用
3. **分类管理：** 表格展示所有分类（含层级关系），支持新增/编辑/删除
4. **预算管理：** 表格展示所有预算，显示已花费/状态，支持新增/删除

---

## 默认数据

### 默认账户（注册时自动创建）

| 名称 | 类型 | 图标 | 颜色 |
|------|------|------|------|
| 现金 | cash | 💵 | #52c41a |
| 微信钱包 | wechat | 💚 | #07c160 |
| 支付宝 | alipay | 💙 | #1677ff |
| 银行卡 | bank | 🏦 | #722ed1 |
| 信用卡 | credit_card | 💳 | #ff4d4f |

### 默认分类（注册时自动创建）

**支出分类（13个顶级，60+子分类）：**

| 顶级分类 | 图标 | 子分类 |
|----------|------|--------|
| 餐饮 | 🍜 | 早餐、午餐、晚餐、外卖、奶茶零食、聚餐、水果 |
| 交通 | 🚗 | 公交地铁、打车、共享单车、加油、停车费、过路费、火车飞机 |
| 购物 | 🛒 | 日用品、衣服鞋帽、数码电子、护肤美容、家居家装、家电 |
| 居住 | 🏠 | 房租、房贷、水电燃气、物业费、装修维修、网费 |
| 娱乐 | 🎮 | 电影、游戏、旅游、运动健身、KTV、会员订阅 |
| 医疗 | 💊 | 门诊、药品、体检、牙科、保健养生 |
| 教育 | 📚 | 书籍、培训课程、学费、考试 |
| 通讯 | 📱 | 手机话费、宽带 |
| 人情 | 🎁 | 红包、礼物、请客、份子钱 |
| 亲子 | 👶 | 奶粉尿布、玩具、早教、学费 |
| 宠物 | 🐾 | 宠物食品、宠物医疗、宠物用品 |
| 其他支出 | 📌 | 杂费、罚款、捐赠 |
| 还信用卡 | 💳 | （无子分类，还信用卡专用） |

**收入分类（4个顶级，16个子分类）：**

| 顶级分类 | 图标 | 子分类 |
|----------|------|--------|
| 工资收入 | 💰 | 工资、奖金、加班费、绩效 |
| 兼职收入 | 💼 | 兼职、稿费、咨询、外包 |
| 投资收益 | 📈 | 股票、基金、利息、分红、虚拟货币、期货 |
| 其他收入 | 🎉 | 报销、礼金、中奖、退款、补贴、二手转让 |

---

## 默认投资数据

### 系统预设资产类型（迁移时自动创建）

| 名称 | 代码 | 大类 | 图标 | 颜色 |
|------|------|------|------|------|
| 股票 | stock | security | 📈 | #1677ff |
| 基金 | fund | security | 📊 | #52c41a |
| 债券 | bond | fixed_income | 📜 | #13c2c2 |
| 黄金 | gold | commodity | 🥇 | #ffc53d |
| 房产 | real_estate | real_estate | 🏠 | #eb2f96 |
| 定期存款 | fixed_deposit | fixed_income | 🏦 | #597ef7 |
| 保险 | insurance | insurance | 🛡️ | #95de64 |
| 虚拟货币 | crypto | other | 🪙 | #faad14 |
| 期货 | futures | other | 📉 | #722ed1 |

---

## 管理命令

### `init_categories`

为用户初始化预置分类数据，幂等操作（已存在的不重复创建）。

```bash
python manage.py init_categories                  # 所有用户
python manage.py init_categories --username admin  # 指定用户
```

### `update_stock_prices`

自动获取所有A股持仓的最新价格，保存每日快照并更新持仓。

```bash
python manage.py update_stock_prices              # 所有用户（仅交易日执行）
python manage.py update_stock_prices --force      # 强制执行（忽略交易日判断）
python manage.py update_stock_prices --user-id 1  # 指定用户
python manage.py update_stock_prices --dry-run    # 仅预览，不写入数据库
python manage.py update_stock_prices --symbol 600519  # 仅更新指定代码
```

**交易日判断：** 工作日（周一至周五）+ 中国法定节假日排除（内置2025-2026年A股休市日历）。

**定时任务：** 在 `settings.py` 中设置 `AUTO_UPDATE_STOCK_PRICES = True` 启用 APScheduler 自动定时任务，工作日 16:05（CST）自动执行价格更新。

---

## 关键行为说明

1. **账户余额手动维护：** 在 TransactionViewSet 的 `_update_account_balance()` 中管理，创建时更新，修改时先回滚旧值再应用新值，删除时回滚。非数据库触发器。
2. **投资持仓自动更新：** 创建投资交易时，买入自动建仓或更新均价，卖出自动减仓，分红降低成本基准，再投资自动买入，拆股按比例调整。在 `services.py` 的 `update_holding_from_transaction()` 中处理。
3. **多币种自动换算：** 投资账户支持独立币种，通过 `ExchangeRate` 表手动录入汇率，`services.py` 的 `to_cny()` 自动换算为人民币汇总。持仓继承账户币种，也支持独立设置。
4. **分红自动处理：** 创建 `DividendRecord` 时自动生成关联 `InvestmentTransaction`，现金分红增加账户余额并降低成本，再投资自动生成买入交易，在 `services.py` 的 `handle_dividend()` 中处理。
5. **批量价格更新：** `batch_update_prices` 接口先将所有持仓的 current_price 复制到 previous_close_price，再设置新价格，确保日盈亏计算正确。
6. **借贷状态自动流转：** 录入还款时自动累加已还金额，全额还清时状态从 outstanding → settled。在 RepaymentViewSet 的 `perform_create` 中处理。
7. **注册自动初始化：** 新用户注册时调用 `init_default_data()` 创建全部默认分类和账户。
8. **报表支持历史数据：** 资产负债表接口可传 `date` 参数查看历史某天的数据，通过回算未来交易实现。投资持仓支持多币种，报表自动换算为人民币。
9. **全局数据隔离：** 所有 ViewSet 的 `get_queryset()` 都按 `request.user` 过滤，非管理员只能看到自己的数据。
10. **前端API代理：** Vite 开发服务器将 `/api` 请求代理到 Django 后端（`127.0.0.1:8000`），生产环境需配置 Nginx 反向代理。
11. **资产类型管理：** 9 个系统预设类型（user=null，不可修改删除），用户可自建扩展。
12. **自动行情获取：** 通过东方财富 kline API（`push2his.eastmoney.com`）获取A股最新价格和昨收价。使用代理优先+直连回退策略，代理池从 GitHub 免费列表获取并并行验证。
13. **手续费自动计算：** 买入/卖出交易自动按券商标准费率计算手续费：佣金万2.5（最低5元）、印花税0.05%（仅卖出）、过户费0.001%（双向）。代码在 `fee_calculator.py`。
14. **每日持仓快照：** 每次价格更新时自动保存 `DailyHoldingSnapshot`，记录当日的收盘价、市值、盈亏等，支持历史盈亏查询。
15. **定时任务：** 通过 APScheduler（BackgroundScheduler）在工作日 16:05 CST 自动执行 `update_stock_prices` 管理命令，在 Django 进程启动时自动注册（`apps.py` 的 `ready()` 方法）。
16. **代理IP系统：** `proxy_pool.py` 从 GitHub 免费代理列表（TheSpeedX/PROXY-List、proxifly 等）获取代理，10线程并行验证，300秒缓存。所有外部请求（行情获取、证券搜索）使用代理优先策略，失败自动回退直连。
17. **投资账户总资产：** `InvestmentAccountSerializer` 计算属性 `total_assets = balance + 总持仓市值`，前端账户卡片直接展示。
