# 模型

本项目只保留 `models/main/` 一个 HEC-RAS 7.0.1 工程，共 5 个 plan：

- p01 `Current`
- p02 `Protect05`
- p03 `Protect10`
- p04 `Protect20`
- p05 `DesignBedCAD`

所有 plan 使用 `Q=26000 m³/s`、下游 Known WS `22.049342 m`、亚临界稳定流。p01-p04 使用现状桥下断面，p05 使用 CAD 01 直接设计河床。

`p01.hdf`--`p05.hdf` 是 2026-08-30 使用当前五工况输入统一计算得到的最终结果快照，已纳入版本控制。几何缓存 `g##.hdf`、`.O##`、`.r##` 和日志属于 HEC-RAS 可再生产物，不纳入仓库。

若基础资料或模型输入发生变化，重新在 HEC-RAS 中计算 p01-p05，再运行 `make results` 更新结果。
