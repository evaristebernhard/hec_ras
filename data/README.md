# 数据

当前水力模型只直接使用 `data/processed/`：

- `processed/cross_sections/`：上游500 m、上游100 m、桥下、下游100 m、下游500 m 五个实测断面；
- `processed/design_bed/西支桥下_设计河床.csv`：CAD 01 中 `中地面线（建设期)` 的直接设计河床；
- `processed/design_bed/` 其余 CSV：标签/引线/实体及 15#/16#/17# 控制值的来源证据。

`data/raw/cad/` 和 `data/intermediate/dxf/` 是本地源文件/中间文件，不进入 Git。只有原始 CAD 或断面发生变化时，才需要重新运行 `extract_cross_sections.py` 或 `recover_design_bed.py`。

当前设计河床不是人工拟合方案。旧“中心/局部/分布”重建已删除，不再属于本项目。
