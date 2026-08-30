# 模型层

- `main/`：p01–p05 主五工况，p06–p07 设计河床重建敏感性。
- `boundary_sensitivity/`：五个主几何 × 三个下游控制水位，共 15 个 plan。

Git 跟踪 HEC-RAS 文本输入和审计表；`.hdf`、`.O##`、`.r##` 是本地计算产物。活动结论以通过自动验收的 HDF 提取结果为准，而不是以输入文件名或进程退出码为准。

运行 `make model-inputs` 后必须外部重算 HEC-RAS，再运行 `make extract-results`；不要把旧 HDF 与新输入组合使用。
