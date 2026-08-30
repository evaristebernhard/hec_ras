# 对外交付

- `cad/design_bed/`：设计河床 DXF、R2004 DWG 兼容副本、权威 CSV、往返校验和人工审阅补充件；
- `ganjiang_design_bed_cad_delivery.zip`：由 `scripts/package_design_bed_delivery.py` 生成的确定性打包件。

权威几何顺序、坐标回写关系和格式限制见 `cad/design_bed/README.md`。`manual_review/` 不是生成目录，打包脚本只读取、不覆盖。
