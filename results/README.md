# 结果层

## 当前活动结果

- `hecras_steady_four_cases.csv`：现状及 0.5/1.0/2.0 m 防护的五断面 v2 HEC-RAS 结果；
- `hecras_steady_four_cases_baseline_v2_20260830.csv`：p01–p04 冻结 WSE 基线；
- `hecras_p01_p04_parity_v2.csv`：p01–p04 逐断面 parity 记录；
- `hecras_design_bed_cad_direct_hdf_audit.csv`：p05 HDF 与 CAD 01 直接设计河床的逐点几何一致性验收；
- `hecras_design_bed_cad_direct_backwater.csv`：通过几何验收后的 p05 关键断面结果；
- `hecras_boundary_sensitivity.csv`：下游水位 ±0.50 m 历史计算明细，其中**仅 Current/Protect05/Protect10/Protect20 行仍作为当前结论使用**。

## 已退役结果

旧 `hecras_design_bed_sensitivity.csv` 以及边界敏感性 CSV 中旧 `DesignBed` 行来自中心/局部型/分布型受约束重建。由于 CAD 01 现已直接恢复完整建设期设计河床，这些结果不再属于活动证据链。

旧重建资料应从 `archive/legacy_constrained_reconstruction/` 查阅，而不应重新引用到当前报告。

## 交叉校核

`cross_checks/` 中的 Python 标准步法/其他独立计算只用于量级检查，不覆盖 HEC-RAS。当前 CAD 直接设计河床的标准步法 RS 600 相对现状约为 +227.4 mm；正式 HEC-RAS p05 为 +193.6 mm。

## 当前求解器文件缺口

`models/main/GanjiangWestBridge.p01.hdf` 当前缺失，因此完整五 plan 活体 HDF 提取暂时不能执行。p01–p04 仍使用已经冻结和验证过的 v2 CSV；最终归档前应补回或重算 p01 HDF。