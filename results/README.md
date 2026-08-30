# 结果

当前只保留由同一批 p01--p05 HDF 直接提取的两份最终结果：

- `hecras_five_cases.csv`：5 个 plan × 5 个断面的详细 HEC-RAS 结果；
- `hecras_five_cases_summary.csv`：RS600 壅水及 RS500 水位、平均流速、过流面积和 Froude 汇总。

五个 HDF 均通过“计算完成且无 warning/error”检查；p05 还通过 RS500 与 CAD01 直接设计河床的逐点几何一致性检查。

重新提取：

```bash
make results
```
