# Home Assistant 用电仪表盘

适用于本集成 v1.3.0 及以上版本。需要通过 HACS 安装并加载 `button-card` 与 `apexcharts-card` 前端资源。

1. 在开发者工具中找到实际电量实体。将两个 YAML 文件内所有 `sensor.csgaccount_example_account_example_account_` 替换为自己的完整账号前缀，保留后面的指标后缀。
2. `electricity_dashboard.yaml` 是模板传感器 package。若已启用 `homeassistant.packages`，把它放入对应 packages 目录；否则将其中 `template` 配置合并到现有模板配置。已有同名模板传感器时应更新原定义，避免重复安装。
3. 将 `electricity.yaml` 放到 `/config/dashboards/electricity/electricity.yaml`。它使用 JSON 格式表达合法 YAML，可直接作为 YAML 仪表盘配置。
4. 在现有 `lovelace.dashboards` 下合并如下条目，不要覆盖其他仪表盘：

```yaml
dashboard-electricity:
  mode: yaml
  title: 用电统计
  icon: mdi:lightning-bolt
  show_in_sidebar: true
  filename: dashboards/electricity/electricity.yaml
```

更新配置后先执行 Home Assistant 配置检查，再按改动范围重载模板或重启 HA，并强制刷新浏览器。

本月只显示用电量、实际报告日期、日均及同期电量比较；费用只取上月和年度已出账数据。同期比较要求两个月第 1 至 N 天均完整，否则不显示百分比。真实零值保留，缺失值不填零。

运行 `node verify_dashboard.cjs` 可验证卡片、缺失状态、真实零值、日期缺口、账期和跨月图表。
