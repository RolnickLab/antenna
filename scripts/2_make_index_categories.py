import numpy as np
import pandas as pd


def numbered_list_to_numpy(list_string):
    # Split the string into lines
    lines = list_string.strip().split("\n")

    # Remove whitespace from each line
    items = [line.strip() for line in lines]

    return np.array(items)


df = pd.read_csv("make_index.csv")
# print(df.shape)

# split into separate csv
idx = int(df.shape[0] / 2)
df1 = df.iloc[:idx]
df2 = df.iloc[idx:]

df1.to_csv("make_index_1.csv")
df2.to_csv("make_index_2.csv")

# Follow the instructions in scripts/README.md about what
# Claude prompt to use to generate categories make_index_1 and make_index_2.

# NOTE: You could have Claude output a list of categories and manually add it to the csv yourself.
# df1_categories = """
# Refactoring
# Functionality Enhancement
# Functionality Enhancement
# Refactoring
# Security/Access Control
# Security/Access Control
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Security/Access Control
# Security/Access Control
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Optimization
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Optimization
# Optimization
# Optimization
# Optimization
# Optimization
# Refactoring
# Refactoring
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Security/Access Control
# Optimization
# Optimization
# Functionality Enhancement
# Refactoring
# Refactoring
# Refactoring
# Refactoring
# Refactoring
# Refactoring
# Refactoring
# Refactoring
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Refactoring
# Functionality Enhancement
# Optimization
# Optimization
# Refactoring
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# """

# df2_categories = """
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Optimization
# Optimization
# Optimization
# Functionality Enhancement
# Functionality Enhancement
# Refactoring
# Functionality Enhancement
# Security/Access Control
# Security/Access Control
# Security/Access Control
# Security/Access Control
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Functionality Enhancement
# Other
# """

# df1_categories = numbered_list_to_numpy(df1_categories)
# df2_categories = numbered_list_to_numpy(df2_categories)

# categories = np.concatenate((df1_categories, df2_categories))

# results = pd.concat([df1, df2], axis=0, ignore_index=True)
# print(df1.shape)
# print(df2.shape)
# print(results.shape)
# print(categories.shape)
# results["Category"] = categories

# results.to_csv("categories.csv")
