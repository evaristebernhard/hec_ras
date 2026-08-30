# 数据层

- `raw/cad/`：四份原始 DWG，本地保存、Git 忽略；`.gitkeep` 只保留目录契约。
- `intermediate/dxf/`：由 `scripts/convert_cad_sources.py` 生成的可解析 DXF，本地保存、Git 忽略。
- `processed/cross_sections/`：五条结构化实测断面和提取摘要。
- `processed/design_bed/`：CAD 01 直接设计河床、标签/引线/实体证据、15#/16#/17# 控制值核验与面积审计。
- `processed/evidence/`：DXF 清单、桥梁几何文本命中和 CAD 转换哈希。

当前活动设计河床为 `processed/design_bed/西支桥下_设计河床.csv`：它直接来自 CAD 01 中 `中地面线（建设期)` 所指向的完整河床折线，不是人工约束重建。

旧版中心型、局部型、分布型河床及其约束审计已经移入 `archive/legacy_constrained_reconstruction/`，仅供历史追溯。活动脚本、模型、结果、报告和 CAD 交付不得再引用这些旧几何。

原始事实与模型解释继续分层保存：CAD 实体/表格证据负责回答“图纸里有什么”，`西支桥下_设计河床.csv` 负责回答“CAD 完整线变换到 HEC-RAS station/elevation 后是什么”，HEC-RAS HDF 审计负责回答“求解器实际算的是否就是这条线”。
