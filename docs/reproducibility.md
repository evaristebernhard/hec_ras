# 复现说明

## 1. 环境和本地输入

Python 依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

独立 Python/STREAM-1D 交叉校核不是主证据链，需要时另装：

```bash
.venv/bin/pip install -r requirements-cross-checks.txt
```

四份原始 DWG 放入 `data/raw/cad/`。大体积原始/中间 CAD 文件不进入 Git；结构化证据 CSV、模型文本输入和提取后的结果表进入版本控制。

## 2. 分阶段流水线

### A. 原始 CAD → 中间 DXF

需要 GNU LibreDWG：

```bash
.venv/bin/python scripts/convert_cad_sources.py
```

脚本只转换声明的源图，不清空目录，并将源/目标 SHA-256 写入 `data/processed/evidence/cad_conversion_manifest.csv`。

### B. DXF → 结构化断面与设计河床证据

```bash
make processed
make evidence
```

`processed` 完成两件核心工作：

1. 从五断面 CAD 提取现状断面；
2. 从 CAD 01 中按 `中地面线（建设期)` 标签 → 引线 → 完整折线直接恢复设计河床。

当前流程**不会生成中心/局部型/分布型三种受约束重建**。旧方法仅保存在 `archive/legacy_constrained_reconstruction/`。

设计河床直接证据包括：

- `西支桥下_设计河床.csv`；
- `design_bed_line_evidence.csv`；
- `design_bed_control_mapping.csv`；
- `design_bed_cad_evidence.csv`；
- `design_bed_direct_audit.csv`。

### C. 结构化证据 → HEC-RAS 输入

```bash
make model-inputs
```

主工程仅生成五个活动工况 p01–p05，其中 p05 使用 CAD 01 直接设计河床。

边界敏感性工程仍生成 5 种几何 × 3 个下游 Known WS，共 15 个 plan。注意：只要执行过 `make model-inputs`，对应旧 HDF 就可能与新文本输入不一致，必须在 HEC-RAS 7.0.1 中重新计算后才能作为当前证据。

### D. HDF 几何一致性与结果提取

如果五个主 plan 的 `.p##.hdf` 都存在，可执行：

```bash
make extract-results
```

主提取器不仅读取结果，还验证：

- `SI Units`；
- RS 500 `Obstr Block Mode=1`；
- `Finished Steady Flow Simulation`；
- 计算信息无 warning/error；
- p01–p04 与冻结 v2 基线的逐断面 parity。

为了避免“p05 文件名是 DesignBedCAD、但 HDF 里仍是旧河床”的静默错误，另有独立几何审计：

```bash
.venv/bin/python scripts/audit_hecras_design_bed_geometry.py
```

它把 p05 HDF 的 RS 500 station/elevation 与活动 CAD 直接河床逐点比较，并输出：

- `results/hecras_design_bed_cad_direct_hdf_audit.csv`；
- `results/hecras_design_bed_cad_direct_backwater.csv`。

当前工作区缺少 `GanjiangWestBridge.p01.hdf`，因此完整 `make extract-results` 暂时会在 p01 阶段停止；p05 独立几何审计可以正常运行。最终归档前应补回或重算 p01 HDF。

### E. 报告与 CAD 交付

报告数据生成应只使用：

- p01–p04 冻结/验证结果；
- 经几何审计通过的 p05 HDF；
- p01–p04 有效的下游边界敏感性结果。

旧受约束重建的设计河床敏感性以及旧 DesignBed 边界结果不得混入当前报告。

CAD 交付只输出 CAD 01 直接设计河床，不再输出三方案重建。

## 3. 设计河床面积差异如何复现

运行：

```bash
.venv/bin/python scripts/recover_design_bed.py
```

`design_bed_direct_audit.csv` 会得到：

- WSE 22.190 m 下 CAD 直接毛面积约 5934.568 m²；
- 扣除 280 m² 后净面积约 5654.568 m²；
- 与表列 5980/5700 m² 相差约 45.432 m²。

该检查采用 `CAD_DIRECT_PRECEDENCE`，表示完整 CAD 几何优先；脚本不会为了满足表格面积重新优化河床。

## 4. 外部 HEC-RAS 计算边界

文本输入由本仓库生成，但 HEC-RAS 7.0.1 求解仍是外部步骤。输入一旦变化，必须明确区分：

- `[INPUT CURRENT / HDF STALE]`：输入已更新，但相应 HDF 尚未重算；
- `[HDF GEOMETRY VERIFIED]`：HDF 中几何与活动输入逐点一致；
- `[PARITY VERIFIED]`：p01–p04 与冻结 v2 基线一致且 HDF 验收通过。

对 CAD 直接设计河床，是否可使用某个 HEC-RAS 数值首先取决于 `audit_hecras_design_bed_geometry.py` 是否通过，而不是仅看 plan 名称或修改时间。