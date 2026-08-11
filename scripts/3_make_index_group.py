import pandas as pd

df = pd.read_csv("categories.csv")
df = df.drop(columns=["Unnamed: 0"])

# print(df.shape)

# split into separate csv, only use context and category and filename
idx = int(df.shape[0] / 2)
df1 = df.iloc[:idx]
df2 = df.iloc[idx:]

df1.to_csv("make_index_1.csv")
df2.to_csv("make_index_2.csv")

# Follow the instructions in scripts/README.md about what Claude prompt
# to use to generate groups for make_index_1 and make_index_2.
