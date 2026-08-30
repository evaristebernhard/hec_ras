# 赣江西支桥位 HEC-RAS 五工况

这个仓库现在只做一件事：用 HEC-RAS 7.0.1 一维稳定流比较 **5 个工况**。

| Plan | 工况 | RS 500 河床 | 等效阻水面积 |
|---|---|---|---:|
| p01 | 现状 | 实测河床 | 360 m² |
| p02 | 0.5 m 防冲刷 | 实测河床 | 380 m² |
| p03 | 1.0 m 防冲刷 | 实测河床 | 390 m² |
| p04 | 2.0 m 防冲刷 | 实测河床 | 410 m² |
| p05 | 设计河床 | CAD 01 `中地面线（建设期)` 直接提取 | 280 m² |

统一计算条件为 `Q=26,000 m³/s`、Manning `n=0.030`、下游 Known WS `22.049342 m`、亚临界稳定流。

## 当前结论

桥上游约 100 m（RS 600）相对现状的水位变化：

- 0.5 m 防护：`+2.525 mm`
- 1.0 m 防护：`+3.803 mm`
- 2.0 m 防护：`+6.382 mm`
- CAD 01 直接设计河床：`+193.558 mm`

设计河床不是以前人工构造的“中心/局部/分布”三方案。CAD 01 中已经找到完整 `中地面线（建设期)`，并且与 15#/16#/17# 的 4.27 / 5.40 / 9.56 m 设计泥面控制值一致。

## 仓库现在只有一条主线

```text
CAD/断面证据
    ↓
五个结构化断面 + CAD01 设计河床
    ↓
models/main/ 五个 HEC-RAS plan
    ↓
HEC-RAS Compute 生成 p01-p05.hdf
    ↓
scripts/extract_hecras_results.py
    ↓
results/hecras_five_cases*.csv
```

不再维护 15-plan 下游边界敏感性、旧三种设计河床重建、Python 标准步法交叉校核或多层自动审计链。

## 只保留 5 个 Python 文件

- `scripts/extract_cross_sections.py`：从五断面 DXF 提取五个实测断面；只有原始断面变化时才需要运行。
- `scripts/recover_design_bed.py`：从 CAD 01 恢复直接设计河床；只有 CAD 源图变化时才需要运行。
- `scripts/build_hecras_project.py`：生成 p01-p05 五工况 HEC-RAS 文本输入。
- `scripts/extract_hecras_results.py`：从 p01-p05 HDF 验证并提取最终结果。
- `scripts/export_design_bed_cad.py`：需要重新导出设计河床 DXF 时使用。

## 正常使用

第一次或模型输入改变时：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
make model
```

然后在 Windows HEC-RAS 7.0.1 中打开：

```text
models/main/GanjiangWestBridge.prj
```

依次计算 p01-p05。HEC-RAS 会自动生成：

```text
GanjiangWestBridge.p01.hdf
...
GanjiangWestBridge.p05.hdf
```

五个 HDF 都存在后运行：

```bash
make results
```

会生成：

- `results/hecras_five_cases.csv`：五工况 × 五断面的详细结果；
- `results/hecras_five_cases_summary.csv`：五工况关键指标汇总。

p01--p05 已在 HEC-RAS 7.0.1 中使用当前输入统一重新计算，五个 `p##.hdf` 已归档并由同一提取脚本生成最终结果。当前不再使用旧四工况/单独 p05 的过渡结果。

## 目录

- `data/processed/`：五断面和 CAD01 设计河床；
- `models/main/`：唯一 HEC-RAS 工程；
- `results/`：当前水力结果；
- `report/`：已有 LaTeX/PDF 报告；
- `deliverables/cad/design_bed/`：设计河床 DXF/DWG 交付成果；
- `docs/project.md`：模型假设、结果解释和剩余资料缺口。

当前模型是**一维等效阻水筛选模型**。它适合比较整体壅水和断面平均流速，不用于桥墩局部最大流速、局部冲刷、压力流或二维流场结论。
