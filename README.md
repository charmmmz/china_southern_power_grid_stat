# China Southern Power Grid Statistics

# 南方电网电费数据HA集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/charmmmz/china_southern_power_grid_stat)](https://github.com/charmmmz/china_southern_power_grid_stat/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

本仓库基于 [CubicPill/china_southern_power_grid_stat](https://github.com/CubicPill/china_southern_power_grid_stat)
维护，继续兼容新版 Home Assistant，并针对南方电网接口的异常日数据补充校验和纠正能力。

## 支持功能

- ✅支持南方电网覆盖范围内的电费数据查询（广东、广西、云南、贵州、海南）
- ✅支持使用手机号、短信验证码和密码（可选）登录，支持南网在线APP、微信、支付宝扫码登录
- ✅支持多个南网账户（每个账户一个集成），支持单个账户下的多个缴费号
- ✅数据自动抓取和更新（默认间隔4小时，可配置）
- ✅全程GUI配置，无需编辑yaml进行配置（暂不支持yaml配置）
- ✅兼容新版 Home Assistant 的集成选项页面
- ✅拦截负用电量、非有限值、重复日期和月份错配等异常数据
- ✅用电日历提供每日电量，已出账月账单提供电费，互不混用
- ✅支持按缴费号和结算日期修正已由南网在线 App 确认的异常日数据

可接入如下数据：

- 当前余额和欠费
- 昨日用电量（仅在日历确实提供昨日数据时可用）
- 最近一日用电量及其实际日期
- 本月、上月累计及逐日用电量（用电日历，数据有延迟）
- 上月已出账电费、账单月份及账单电量
- 本年度、上年度已出账的累计及每月电费、用电量

本月电费、每日电费和阶梯档位/剩余电量/电价不再提供；旧实体保留为不可用以保留历史，
新安装默认禁用这些实体。不会根据历史平均单价推算费用，也不会将缺失数据写成 0。
不支持峰谷电价设置、阶梯配置或电费估算。

❌因为南网登录API调整，不再支持登录态失效之后自动重新登录，需要手动重新登录。

## 使用方法

### HACS 自定义仓库

本 fork 不属于 HACS 默认仓库，需要先添加为自定义仓库：

1. 打开 HACS → 集成。
2. 在右上角菜单中选择“自定义存储库”。
3. 添加 `https://github.com/charmmmz/china_southern_power_grid_stat`，类别选择“集成”。
4. 搜索并安装 **China Southern Power Grid Statistics**，然后重启 Home Assistant。

也可以从 [GitHub Releases](https://github.com/charmmmz/china_southern_power_grid_stat/releases)
下载对应版本，手动复制 `custom_components/china_southern_power_grid_stat` 到 Home Assistant 配置目录。

注意：本集成要求 `Home Assistant` 最低版本为 `2022.11`。

### 数据口径与异常处理

可选的 Home Assistant 仪表盘和 Tesserae 用电组件见 [仪表盘示例](examples/README.md)。
它们需要单独配置，HACS 升级集成不会自动替换已有仪表盘。

每日用电量来自 App 通道的 `charge/queryElectricityCalendar`，按接口给出的日期归属，
并按中国时区判断昨日和月份。空白日期代表尚未提供，不是 0 kWh。月度传感器提供
`latest_day_date`、`reported_days`、`usage_month`、`data_source`，便于界面显示数据进度。

上月电费从年度账单中严格匹配上一个自然月，跨年时读取上年度；账单未出时为不可用。
费用实体的 `billing_month` 标明账期，`billing_kwh` 是该账单的电量。
日历累计电量与账单电量可能有精度或结算差异，不应合并或互相替代。
年度累计同样是已出账数据，不包含本月未出账费用。

负用电量、非数字、非有限值、重复日期、错误月份或未来日期不会发布到 Home Assistant。
单个来源失败不会隐藏另一来源的有效数据。月度电量的 `data_quality` 标明 `api`、
`corrected` 或 `unavailable`；`applied_corrections` 列出本次应用纠正的日期。

### 可选：修正南网已确认的异常日数据

如果南网接口返回了明显错误的负用电量，而南网在线 App 已显示正确值，可以在
Home Assistant 配置目录创建 `china_southern_power_grid_stat_corrections.json`：

```json
{
  "accounts": {
    "缴费号": {
      "2026-08-19": {"kwh": 25.51}
    }
  }
}
```

集成会在刷新时应用修正并根据逐日数据重算月累计值。未配置修正时，含负用电量的
数据源会被拒绝，而不会将负数发布到 Home Assistant。

### 配置界面

支持的登录方式

<img src="https://raw.githubusercontent.com/charmmmz/china_southern_power_grid_stat/master/img/setup_login.png" alt="" style="width: 400px;">

配置界面

<img src="https://raw.githubusercontent.com/charmmmz/china_southern_power_grid_stat/master/img/setup_add_account.png" alt="" style="width: 400px;">

添加缴费号

<img src="https://raw.githubusercontent.com/charmmmz/china_southern_power_grid_stat/master/img/setup_select_account.png" alt="" style="width: 400px;">

传感器列表
- 余额
- 欠费
- 上月电费
- 上月用电量
- 当月用电量
- 本年度电费
- 本年度用电量
- 上年度电费
- 上年度用电量
- 最近日用电量
- 昨日用电量




传感器额外参数（每月用量、每日用量）

<img src="https://raw.githubusercontent.com/charmmmz/china_southern_power_grid_stat/master/img/sensor_attr.png" alt="" style="width: 400px;">

参数设置

<img src="https://raw.githubusercontent.com/charmmmz/china_southern_power_grid_stat/master/img/setup_params.png" alt="" style="width: 400px;">

### 数据更新策略

本月和上月用电日历、本年度账单、余额和欠费跟随配置的更新间隔（默认 4 小时）。
上月数据不再于每月 3 日后停止刷新，以便获取延迟出账和后续更正。
上年度账单每天最多缓存一天，失败后会在下次刷新重试；重载集成会清空此缓存。
昨日和最近日电量直接由已获取的日历推导，不再额外调用失效的昨日/日电费接口。

## 一些技术细节

### 登录接口加密原理

登录接口的请求数据和返回数据都经过加密，其中请求数据经过两层加密：整个请求数据的`AES`加密和密码字段的`RSA`
公钥加密（密钥、公钥具体值见代码）。

加密前的请求数据结构如下：

```json5
{
  "areaCode": "xxx",
  "acctId": "xxx",
  "logonChan": "xxx",
  "credType": "xxx",
  "credentials": "xxx"  // <- encrypted with RSA
}
```

返回数据同样经过`AES`加密，密钥与请求数据相同。但返回值其中暂时不包含有用信息，验证状态码正常后可以直接忽略内容。

### Web端接口和App端接口

对于南网API相关信息的提取主要通过Web端的抓包和JS代码获取。
之后因为登录态有效期问题，对App端抓包进行比对后切换到App端API。
经过验证，Web端（网上营业厅）和App端（南网在线）的API接口基本相同，差别主要在于：

|              | Web                        | App                     |
|--------------|----------------------------|-------------------------|
| API路径        | ucs/ma/wt/                 | ucs/ma/zt/              |
| 支持登录方式       | 手机号+验证码（+密码），南网在线/微信/支付宝扫码 | 手机号+验证码（+密码），微信/支付宝跳转登录 |
| token有效期     | 几小时（有待进一步确认）               | 较长（有待进一步确认）                      |
| Cookies      | token包含在cookies中           | 无cookies                |
| 敏感信息（姓名、地址等） | 部分信息用“*”隐去                 | 有明文全文                   |

另外在HTTP请求头上有细微的差别（如：UA），但实际上对于请求的返回结果没有影响。

### API 实现库

本项目代码中的[`csg_client/__init__.py`](https://github.com/charmmmz/china_southern_power_grid_stat/blob/master/custom_components/china_southern_power_grid_stat/csg_client/__init__.py)
是对南网在线 App API 的实现，可以独立于此项目单独使用。
详细使用方法见`csg_client_demo.py`

## Thank you
- [lyylyylyylyy](https://github.com/lyylyylyylyy): PR [#30](https://github.com/CubicPill/china_southern_power_grid_stat/pull/30) 短信验证码登录支持

感谢[瀚思彼岸](https://bbs.hassbian.com/)论坛以下帖子作者的辛苦付出，排名不分先后

- [不折腾，超简单接入电费数据](https://bbs.hassbian.com/thread-18474-1-1.html)
- [北京电费查询加强版](https://bbs.hassbian.com/thread-13820-1-1.html)
- [电费插件（Node-Red流）-广东南方电网](https://bbs.hassbian.com/thread-17830-1-1.html)
- [【抄作业】电费插件(NR流)-南网](https://bbs.hassbian.com/thread-18122-1-1.html)

自定义集成教程参考：[Building a Home Assistant Custom Component Part 1: Project Structure and Basics](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_1/)



