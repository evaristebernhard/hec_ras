# 模型

只保留 `models/main/` 一个 HEC-RAS 工程，共 5 个 plan：

- p01 `Current`
- p02 `Protect05`
- p03 `Protect10`
- p04 `Protect20`
- p05 `DesignBedCAD`

所有 plan 使用 `Q=26000 m³/s`、下游 Known WS `22.049342 m`、亚临界稳定流。p01-p04 使用现状桥下断面，p05 使用 CAD 01 直接设计河床。

`.prj/.p##/.g##/.f##` 是版本控制输入；`.hdf/.O##/.r##` 是 HEC-RAS 本地计算产物，不提交 Git。

重新生成文本输入：

```bash
make model
```

然后在 HEC-RAS 7.0.1 中打开 `models/main/GanjiangWestBridge.prj` 并计算 p01-p05。
