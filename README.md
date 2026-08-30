# 赣江西支桥位一维行洪分析

本仓库回答一个明确问题：在相同流量、糙率、河道断面和下游边界下，桥墩防冲刷增量及设计河床筛选断面对上游水位产生多大影响？

## 已验证结论

在 `Q=26,000 m³/s`、`n=0.030`、下游已知水位 `22.049342 m` 的 HEC-RAS 7.0.1 一维稳定流模型中，RS 600（桥上游约 100 m）相对现状的水位变化为：

| 主工况 | ΔWSE |
|---|---:|
| 0.5 m 防冲刷 | +2.525 mm |
| 1.0 m 防冲刷 | +3.803 mm |
| 2.0 m 防冲刷 | +6.382 mm |
| 设计河床中心重建 | +182.556 mm |

三种合规设计河床重建在 RS 600 的离散范围为 `0.177 mm`；p01–p04 与冻结的 v2 基线逐断面差值均小于 `1×10⁻⁶ m`。**[PARITY VERIFIED]**

这些数值是整体行洪筛选结果，不是局部桥墩流态或冲刷深度结论。设计河床是约束重建，不是原设计院完整断面。

## 第一性原理结构

仓库只保留一条活动证据链：

```text
原始 CAD → 可读 DXF → 可追溯断面/控制点 → 明示假设的模型输入
         → HEC-RAS 活体 HDF 验收 → 结果表 → 报告/交付件
```

| 层级 | 目录 | 唯一职责 |
|---|---|---|
| 原始事实 | `data/raw/` | 本地原始 CAD；大文件不进入 Git |
| 中间表示 | `data/intermediate/` | 可解析 DXF；可由原始 CAD 再生 |
| 结构化证据 | `data/processed/` | 断面、CAD 实体证据、设计河床重建与审计 |
| 模型输入 | `models/` | 主工程和下游边界敏感性工程 |
| 数值结果 | `results/` | HDF 提取结果与自动验收；交叉校核单独隔离 |
| 方法与结论 | `docs/` | 方法、复现、活动结论，不重复保存流水账 |
| 正式报告 | `report/` | `main.tex`、`main.pdf` 及其可再生图表数据 |
| 对外交付 | `deliverables/` | CAD/DWG/CSV/校验清单和确定性 ZIP |
| 历史材料 | `archive/` | 已停用 v1 口径，仅供追溯，禁止被活动流程引用 |

证据优先级为：计算 HDF 与运行消息 > 提取结果 > 模型输入 > 重建脚本 > 说明文档。文档不能推翻已验证的计算行为。

## 入口

- [方法与边界](docs/methodology.md)
- [从空环境复现](docs/reproducibility.md)
- [活动结果与缺口](docs/findings.md)
- [正式 PDF 报告](report/main.pdf)
- [五工况结果](results/hecras_steady_five_cases.csv)
- [设计河床 CAD 交付](deliverables/cad/design_bed/README.md)

## 常用命令

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

make processed       # DXF → 断面与设计河床
make evidence        # CAD 文本/实体索引
make model-inputs    # 重建 HEC-RAS 文本输入；随后必须外部重算
make extract-results # 验收已有 HDF 并提取 CSV
make report          # 重建报告数据、图件和 PDF
make verify          # 活动结构、约束、HDF 结果、parity、交付哈希
```

`make model-inputs` 会改变模型输入，因此不会被 `make verify` 隐式调用。完整的外部 HEC-RAS 执行边界见 [复现说明](docs/reproducibility.md)。

## 尚未闭合的输入

1. 可独立验证的原设计完整河床断面；
2. 桥面、梁底/低弦、净空和完整迎水几何；
3. 正式下游设计控制水位或水位–流量关系；
4. Manning `n=0.030` 的项目最终依据。

在这些输入补齐前，不把当前等效阻水模型包装成显式 Bridge/Culvert、二维局部流态或正式冲刷结论。
