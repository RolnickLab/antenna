import numpy as np
import pandas as pd


def numbered_list_to_numpy(list_string):
    # Split the string into lines
    lines = list_string.strip().split("\n")

    # Remove whitespace from each line
    items = [line.strip() for line in lines]

    return np.array(items)


df = pd.read_csv("/Users/vanessa/dev/mila/ami-platform/make_index.csv")
# print(df.shape)

# split into separate csv
idx = int(df.shape[0] / 2)
df1 = df.iloc[:idx]
df2 = df.iloc[idx:]

df1.to_csv("/Users/vanessa/dev/mila/ami-platform/make_index_1.csv")
df2.to_csv("/Users/vanessa/dev/mila/ami-platform/make_index_2.csv")

# Categories for df1 and df2 are generated using Claude AI with the following prompt:
# This is a csv file with a list of todos from a code base. Each todo's file location,
# function location, line location, and context is given.
# Categorize the todos into the following categories:
# * Functionality Enhancement: Enhancing existing functionality or adding new features.
# * Refactoring: Code reorganization or improving structure.
# * Security/Access Control: Security-related improvements or access control.
# * Optimization: Performance or scalability improvements.
# * Other
# Give the results as a list of categories, corresponding to the order of todos in the csv file
#
#  ... attach csv file of df1 and df2 separately (file too large for claude to process at once)

df1_categories = """
Refactoring
Functionality Enhancement
Functionality Enhancement
Refactoring
Security/Access Control
Security/Access Control
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Security/Access Control
Security/Access Control
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Optimization
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Optimization
Optimization
Optimization
Optimization
Optimization
Refactoring
Refactoring
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Security/Access Control
Optimization
Optimization
Functionality Enhancement
Refactoring
Refactoring
Refactoring
Refactoring
Refactoring
Refactoring
Refactoring
Refactoring
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Refactoring
Functionality Enhancement
Optimization
Optimization
Refactoring
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
"""

df2_categories = """
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Optimization
Optimization
Optimization
Functionality Enhancement
Functionality Enhancement
Refactoring
Functionality Enhancement
Security/Access Control
Security/Access Control
Security/Access Control
Security/Access Control
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Functionality Enhancement
Other
"""

df1_categories = numbered_list_to_numpy(df1_categories)
df2_categories = numbered_list_to_numpy(df2_categories)

categories = np.concatenate((df1_categories, df2_categories))

results = pd.concat([df1, df2], axis=0, ignore_index=True)
print(df1.shape)
print(df2.shape)
print(results.shape)
print(categories.shape)
results["Category"] = categories

results.to_csv("/Users/vanessa/dev/mila/ami-platform/categories.csv")
