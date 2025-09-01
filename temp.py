import pandas as pd

ori_path = "量子智投泰山500增强净值20250828.xlsx"
out_path = "performance_data.csv"

df = pd.read_excel(ori_path)
df = df[['Date','Strategy_Value','Benchmark_Value']]

df.to_csv(out_path, index=False)