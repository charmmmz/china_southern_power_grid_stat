# 可选仪表盘示例

这些示例与集成 v1.3.0 一起发布，不会由 HACS 自动安装，也不会替换已有仪表盘。

- `home-assistant-dashboard/`：Home Assistant 用电仪表盘及模板传感器。账号前缀已替换成占位示例，部署前请按其 README 修改。
- `tesserae/ha_csg_energy/`：Tesserae 用电组件 v0.2.0，包含服务端、显示代码和回归测试。`plugin.json` 中全部为模拟数据。

Home Assistant 的“同期”比较使用两个月相同且完整的日期范围；Tesserae 的日均卡片比较本月已报告天数的日均与上个完整自然月的日均。两个口径的标签和用途不同。

公开源码不包含家庭账号、认证信息、个人仪表盘快照或设备绑定。恢复备份保留在各自部署环境。
