# metro 问题说明

当前的station检测机制是基于轮廓检测, UI检测是基于模板匹配。
现在的assets/stations实际上没用到。使用轮廓检测看不出形状，符合GUI action的逻辑，没有给llm提供太多信息。

## 轮廓检测开关
可以通过配置文件或命令行参数控制轮廓检测功能的启用/禁用：
- 在 `config.yaml` 中设置 `env.enable_contour_detection: true/false`
- 默认值为 `true`（启用）
- 禁用后，将不会检测站点位置，`stations` 列表为空，可以减少计算开销

## 其他说明
