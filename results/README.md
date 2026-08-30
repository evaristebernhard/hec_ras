# 结果

当前在 5 个 HDF 全部重新计算完成前，暂时保留三份现有有效结果：

- `hecras_steady_four_cases.csv`：p01-p04 已验证五断面结果；
- `hecras_design_bed_cad_direct_backwater.csv`：当前 p05 CAD01 直接设计河床关键结果；
- `hecras_design_bed_cad_direct_hdf_audit.csv`：当前 p05 HDF 与 CAD01 河床几何一致性记录。

当 `models/main/GanjiangWestBridge.p01.hdf` 到 `p05.hdf` 全部重新计算后，运行：

```bash
make results
```

新的简化提取器会直接生成：

- `hecras_five_cases.csv`：5 个 plan × 5 个断面的完整结果；
- `hecras_five_cases_summary.csv`：每个工况的 RS600 壅水与 RS500 流速/Froude 汇总。

之后上述三份过渡文件也可以删除，只保留两个五工况结果文件。
