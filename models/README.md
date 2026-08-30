# 模型层

- `main/`：p01–p05 主五工况。p01=现状，p02/p03/p04=0.5/1.0/2.0 m 防护，p05=`DesignBedCAD`，直接使用 CAD 01 的建设期设计河床。
- `boundary_sensitivity/`：五个主几何 × 三个下游控制水位，共 15 个 plan；其中 p05/p10/p15 分别为 `DesignBedCAD_Low/Base/High`。

活动模型不再包含 p06–p07 的中心/局部/分布型设计河床重建敏感性；旧文件仅保存在 `archive/legacy_constrained_reconstruction/`。

Git 跟踪 HEC-RAS 文本输入和审计表；`.hdf`、`.O##`、`.r##` 是本地计算产物。活动结论以通过自动验收的 HDF 提取结果为准，而不是以输入文件名或进程退出码为准。

当前状态：主模型 p05 的 HDF 已通过 CAD01 直接河床逐点几何审计；p01 HDF 缺失。边界敏感性文本输入已经更新为 CAD01 直接河床，但新的 `DesignBedCAD_Low/Base/High` 仍需在 HEC-RAS 7.0.1 中重算。

运行 `make model-inputs` 后必须外部重算 HEC-RAS，再运行 `make extract-results`；不要把旧 HDF 与新输入组合使用。具体重算清单见 `docs/solver_handoff.md`。
