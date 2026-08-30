# HEC-RAS 求解器交接与重算清单

本文只列当前活动模型真正需要由 HEC-RAS 7.0.1 求解器完成的工作，避免再次回到已退役的设计河床重建路线。

## 1. 不再做的事情

- 不再构造中心型、局部型、分布型三条设计河床；
- 不再把 5700 m² 当作塑造设计河床几何的硬约束；
- 不再引用旧 p05–p07 受约束重建结果或旧 DesignBed 边界敏感性结果；
- 不需要重新识别 CAD 01 的设计河床，当前活动几何已经由 `中地面线（建设期)` 直接恢复并通过表值与 HDF 几何核验。

## 2. 主五工况：补齐 p01 HDF

工程：`models/main/GanjiangWestBridge.prj`

当前五个 plan：

| plan | Short ID | 状态 |
|---|---|---|
| p01 | Current | 文本输入存在，当前缺 `p01.hdf` |
| p02 | Protect05 | 冻结 v2 结果已验证 |
| p03 | Protect10 | 冻结 v2 结果已验证 |
| p04 | Protect20 | 冻结 v2 结果已验证 |
| p05 | DesignBedCAD | HDF 已通过 CAD01 直接河床逐点几何审计 |

优先动作：在 HEC-RAS 7.0.1 中打开 `GanjiangWestBridge.prj`，重新计算 p01。若方便，建议一次性重算 p01–p05，以便最终归档时从五个活体 HDF 统一提取，而不是混用冻结 CSV 与当前 HDF。

计算完成后运行：

```bash
make extract-results
make verify
make report
```

验收重点：

- `SI Units`；
- RS 500 `Obstr Block Mode=1`；
- `Finished Steady Flow Simulation`；
- 无 warning/error；
- p01–p04 与冻结 v2 基线 parity；
- p05 RS 500 station/elevation 与 CAD01 28 点设计河床逐点一致。

## 3. 下游边界敏感性：更新 CAD01 设计河床结果

工程：`models/boundary_sensitivity/GanjiangWestBridgeBoundary.prj`

当前输入已经是 5 个活动几何 × 3 个下游 Known WS：

- Low = 21.549342 m；
- Base = 22.049342 m；
- High = 22.549342 m。

CAD01 设计河床对应：

| plan | Short ID | 必须重算 |
|---|---|---|
| p05 | DesignBedCAD_Low | 是 |
| p10 | DesignBedCAD_Base | 是 |
| p15 | DesignBedCAD_High | 是 |

现状与三种防护的旧边界结果仍可用于当前定性/定量比较，因为其几何未改变；但为了最终成果内部一致，**推荐一次性重算全部 15 个 plan**，然后重新运行：

```bash
.venv/bin/python scripts/extract_hecras_boundary_sensitivity.py
make verify
make report
```

重算前不要把旧 CSV 中 `DesignBed` 行解释成现在的 CAD01 设计河床。

## 4. 求解后应形成的闭环

完成上述两项后，活动证据链应变为：

```text
CAD01 完整设计河床
  → models/main p05 与 boundary p05/p10/p15
  → HEC-RAS 7.0.1 新 HDF
  → 几何/完成标记/warning 审计
  → 五工况结果 + 新设计河床边界敏感性
  → report/main.pdf
```

届时可以关闭当前两个数值缺口：

1. 主模型 p01 HDF 缺失；
2. CAD01 直接设计河床的下游边界敏感性尚未重算。

## 5. 仍属于资料缺口、不是求解器 bug 的事项

- 正式下游设计控制水位或水位–流量关系；
- Manning `n=0.030` 的项目最终依据；
- 若升级显式桥梁模型：桥面、低弦/梁底、净空、完整桥墩迎水几何。

这些资料没有补齐以前，当前成果保持“一维等效阻水行洪筛选”的定位。
