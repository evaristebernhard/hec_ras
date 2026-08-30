# 赣江西支桥位一维行洪分析

本仓库回答一个明确问题：在相同流量、糙率、河道断面和下游边界下，桥墩防冲刷增量及 CAD 01 直接设计河床对上游水位产生多大影响？

## 已验证结论

在 `Q=26,000 m³/s`、`n=0.030`、下游已知水位 `22.049342 m` 的 HEC-RAS 7.0.1 一维稳定流模型中，RS 600（桥上游约 100 m）相对现状的水位变化为：

| 主工况 | ΔWSE |
|---|---:|
| 0.5 m 防冲刷 | +2.525 mm |
| 1.0 m 防冲刷 | +3.803 mm |
| 2.0 m 防冲刷 | +6.382 mm |
| CAD 01 直接设计河床 | **+193.558 mm** |

CAD 01 中 `中地面线（建设期)` 经“语义标签 → 引线 → 完整 LWPOLYLINE”直接恢复为 28 点设计河床，并与 15#/16#/17# 的 4.27/5.40/9.56 m 设计泥面表值完全一致。p05 HDF 的 RS 500 几何也已与该 28 点断面逐点核验通过。旧版中心/局部/分布型受约束重建已退役，不再属于活动证据链。

三种防护相对现状仍只产生毫米级上游附加壅水；CAD 直接设计河床使 RS 600 水位提高约 0.194 m，并使桥下 RS 500 平均流速提高至约 4.692 m/s。上述结果是一维整体行洪筛选结论，不是局部桥墩流态或冲刷深度结论。

在 WSE=22.190 m 下，CAD 直接河床毛过水面积为 5934.568 m²，扣除 280 m² 等效阻水后净面积为 5654.568 m²；与表列 5980/5700 m² 相差 45.432 m²（约 0.76%）。当前采取 **CAD 完整几何优先**，不再为满足面积表值人工修改河床线。

## 第一性原理结构

仓库只保留一条活动证据链：

```text
原始 CAD → 可读 DXF → 可追溯断面/设计河床证据 → 明示假设的模型输入
         → HEC-RAS 活体 HDF 验收 → 结果表 → 报告/交付件
```

| 层级 | 目录 | 唯一职责 |
|---|---|---|
| 原始事实 | `data/raw/` | 本地原始 CAD；大文件不进入 Git |
| 中间表示 | `data/intermediate/` | 可解析 DXF；可由原始 CAD 再生 |
| 结构化证据 | `data/processed/` | 五断面、CAD 实体证据、CAD01 直接设计河床与审计 |
| 模型输入 | `models/` | 主五工况和下游边界敏感性工程 |
| 数值结果 | `results/` | HDF 提取结果与自动验收；交叉校核单独隔离 |
| 方法与结论 | `docs/` | 方法、复现、活动结论和求解器交接 |
| 正式报告 | `report/` | `main.tex`、`main.pdf` 及其可再生图表数据 |
| 对外交付 | `deliverables/` | CAD/DWG/CSV/校验清单和确定性 ZIP |
| 历史材料 | `archive/` | 已停用 v1 与旧约束重建，仅供追溯，禁止被活动流程引用 |

证据优先级为：计算 HDF 与运行消息 > 提取结果 > 模型输入 > CAD 恢复脚本 > 说明文档。文档不能推翻已验证的计算行为。

## 入口

- [方法与边界](docs/methodology.md)
- [从空环境复现](docs/reproducibility.md)
- [活动结果与缺口](docs/findings.md)
- [HEC-RAS 求解器交接与重算清单](docs/solver_handoff.md)
- [正式 PDF 报告](report/main.pdf)
- [现状及三种防护结果](results/hecras_steady_four_cases.csv)
- [CAD01 设计河床 HDF 关键结果](results/hecras_design_bed_cad_direct_backwater.csv)
- [设计河床 CAD 交付](deliverables/cad/design_bed/README.md)

## 常用命令

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

make processed       # DXF → 五断面与 CAD01 直接设计河床
make evidence        # CAD 文本/实体索引
make model-inputs    # 重建 HEC-RAS 文本输入；随后必须外部重算
make extract-results # 验收已有 HDF 并提取 CSV
make report          # 重建报告数据、图件和 PDF
make verify          # 活动结构、CAD01/p05 几何、parity、交付哈希
```

`make model-inputs` 会改变模型输入，因此不会被 `make verify` 隐式调用。完整的外部 HEC-RAS 执行边界见 [复现说明](docs/reproducibility.md)。

## 当前真正未闭合的工作

1. `models/main/GanjiangWestBridge.p01.hdf` 当前缺失；最终归档前应补回或重算 p01，并再次完成五 plan 活体 HDF 提取。
2. 下游 Known WS ±0.50 m 的旧 DesignBed 结果来自已退役几何；需要用 CAD01 直接设计河床重新计算 `DesignBedCAD_Low/Base/High`，最终归档建议重算全部 15 个边界敏感性 plan。
3. 正式下游设计控制水位或水位–流量关系仍缺少项目依据。
4. Manning `n=0.030` 仍需项目最终依据。
5. 若要升级为显式 Bridge/Culvert 或二维局部流态，还需桥面、梁底/低弦、净空和完整迎水几何。

CAD01 已经解决“是否存在完整设计河床线”的旧缺口；后续不再回到三种人工重建方案。
