# 数据层

- `raw/cad/`：四份原始 DWG，本地保存、Git 忽略；`.gitkeep` 只保留目录契约。
- `intermediate/dxf/`：由 `scripts/convert_cad_sources.py` 生成的可解析 DXF，本地保存、Git 忽略。
- `processed/cross_sections/`：五条结构化断面和提取摘要。
- `processed/design_bed/`：CAD 控制值、桥墩 station、三种设计河床和逐项约束审计。
- `processed/evidence/`：DXF 清单、桥梁几何文本命中和 CAD 转换哈希。

原始事实与推定几何分开存放：`design_bed_cad_evidence.csv` 是 CAD 证据，三份 `西支桥下_设计河床*.csv` 是约束重建结果，不能互相冒充。
