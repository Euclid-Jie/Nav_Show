import pandas as pd

ori_path = "98数据/睿量原子1号净值20250908.xlsx"
out_path = "performance_data睿量原子1号净值20250908.csv"

df = pd.read_excel(ori_path)
df = df[['日期','单位净值']].rename(columns={'日期':'Date','单位净值':'Strategy_Value'})

df.to_csv(out_path, index=False)
