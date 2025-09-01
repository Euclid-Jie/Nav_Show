# Nav_Show 项目说明

## 项目简介

本项目用于展示和分析量化投资产品的净值表现。通过读取本地的净值数据文件（如 Excel 或 CSV），生成可视化的业绩报告，并以网页形式展示。

## 主要文件说明

- `main.py`：主程序，负责数据读取、处理和报告生成。
- `performance_data.csv`：产品净值表现数据（CSV 格式）。
- `量子智投泰山500增强净值20250828.xlsx`：产品净值表现数据（Excel 格式）。
- `performance_report.html`：自动生成的业绩分析报告网页。
- `index.html`：静态网页入口，可用于展示报告或其他内容。
- `temp.py`：临时脚本或测试代码。

## 使用方法

1. **准备数据**：将净值数据文件（CSV 或 Excel）放置于项目根目录。
2. **运行主程序**：
   ```bash
   python main.py
   ```
3. **查看报告**：运行后会生成 `index.html`，可用浏览器打开查看。

## 依赖环境

- Python 3.7 及以上
- 推荐安装以下依赖包：
  - pandas
  - matplotlib
  - openpyxl

可通过如下命令安装依赖：
```bash
pip install pandas matplotlib openpyxl
```

## 许可证

本项目遵循 MIT License。
