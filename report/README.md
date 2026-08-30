# 正式报告

- `main.tex`：唯一活动 LaTeX 源文件；
- `main.pdf`：正式编译成果；
- `data/`、`figures/`：由脚本生成并供 LaTeX 引用的表图数据。

重建：

```bash
make report
```

该目标先从已验收 HDF 重建结果数据，再生成图件并执行两次 XeLaTeX。LaTeX 临时文件不进入 Git。
