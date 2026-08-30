# 赣江西支桥位一维行洪分析

当前状态与结果请先读：[`doc/项目当前状态.md`](doc/项目当前状态.md)。正式计算报告见 [`report/main.tex`](report/main.tex)，编译版为 `report/main.pdf`。

截至 2026-08-30，HEC-RAS 7.0.1 一维稳定流计算已完成：

- 五个主工况：现状河床、0.5 m / 1.0 m / 2.0 m 防冲刷、设计河床筛选方案；
- 两个设计河床重建敏感性工况；
- 下游控制水位 ±0.50 m 的 15-plan 敏感性分析；
- HDF 单位、阻水模式、完成标记及 warning/error 自动验收；
- 等效阻水 v2 修正：22.190 m 仅用于校准阻水面积，阻水顶采用数值哨兵避免人工越顶。

基准下游已知水位 22.049342 m、Q=26,000 m³/s、Manning n=0.030 时，桥上游 100 m（RS=600）相对现状新增壅水为：

- 0.5 m 防护：**+2.525 mm**；
- 1.0 m 防护：**+3.803 mm**；
- 2.0 m 防护：**+6.382 mm**；
- 设计河床筛选方案：**+182.556 mm**。

三种防护在下游水位上下变化 0.50 m 时仍保持毫米级附加壅水。设计河床三种合理重建在关键断面的 WSE 差仅约 0.10–0.18 mm。

> 注意：当前“设计河床线”是依据 CAD 中 15#/16#/17# 设计泥面控制点和 5700 m² 净行洪面积构造的水力筛选断面，不是声称已恢复原设计院完整设计河床线。当前模型也是一维等效阻水模型，不是显式 Bridge/Culvert 或二维局部冲刷模型。

## 主要入口

- 正式 HEC-RAS 工程：`hecras_model/`
- 五工况关键结果：`results/hecras_steady_five_cases.csv`
- 设计河床敏感性：`results/hecras_design_bed_sensitivity.csv`
- 下游边界敏感性：`results/hecras_boundary_sensitivity.csv`
- 当前状态说明：`doc/项目当前状态.md`
- 正式 LaTeX 报告：`report/main.tex`
- 报告 PDF：`report/main.pdf`
- 模型生成：`scripts/build_hecras_project.py`
- HDF 验收与提取：`scripts/extract_hecras_steady_results.py`
- 设计河床恢复：`scripts/recover_design_bed.py`
- 报告数据生成：`scripts/build_report_data.py`

## 报告复现

```bash
.venv/bin/python scripts/recover_design_bed.py
.venv/bin/python scripts/build_report_data.py
cd report
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

## 当前剩余资料缺口

1. 原始/正式设计河床整治线；
2. 桥面、梁底/低弦、桥下净空及完整桥墩迎水尺寸；
3. 正式下游设计控制水位或水位–流量关系；
4. Manning n 的项目最终依据。

上述资料补齐后，才有必要决定是否升级为显式 Bridge/Culvert；只有明确要求局部流速和冲刷评价时，再升级二维模型。
