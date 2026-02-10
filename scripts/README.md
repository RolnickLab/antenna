# Example pipeline
```
python scripts/1_make_index.py --repo_path path_to_ami_repo
```
This will output a file `make_index.csv` with the headers `["File", "Function", "Line Number", "Context"]`.

```
python scripts/2_make_index_categories.py
```
Categories are the "type" of the TODO. This script splits `make_index.csv` into 2 separate csvs (`make_index_1.csv` and `make_index_2.csv`). Attach these files with the claude prompt below. 2 separate input csvs are made due to limits on the Claude free plan.

> This is a csv file with a list of todos from a code base. Each todo's file location, function location, line location, and context is given. Categorize the todos into the following categories:
> * Functionality Enhancement: Enhancing existing functionality or adding new features.
> * Refactoring: Code reorganization or improving structure.
> * Security/Access Control: Security-related improvements or access control.
> * Optimization: Performance or scalability improvements.
> * Other
> Give the results as a csv with the same headers as the input csv, but add a column called 'categories'.

Download the output csvs from claude and combine them into a csv called `categories.csv`. This csv will have headings `["File", "Function", "Line Number", "Context", "Category"]`.

```
python scripts/3_make_index_groups.py
```
Group TODOs that seem to refer to the same TODO in `categories.csv`. Again, this script splits the input csv (`categories.csv`) into 2 separate csvs to be processed by Claude. Use the prompts below.

Claude prompt for make_index_1.csv:
> Given this csv which contains a list of TODOs compiled from a repo. The headers are the file names where each TODO is located, context for each todo,  and the category (functionality enhancement, refactoring, security/access control,  optimization, other). Group the TODOs that appear to refer to the same todo. Output a csv with the same headers as the original csv. but add a column with the  name of the group (or miscelleneous if no group).

Claude prompt for make_index_2.csv: (NOTE: you could add the groupings from make_index_1 or ask Claude to generate new categories)
> Group the todos in this csv I attached if they appear to refer to the same todos. Make a csv which I can download which contains the same columns as the csv but with an additional group column. The groups can be as follows, but you can add new groups if it doesn't fit into any of these well:
> - miscellaneous
> - Optimize S3 Operations
> - improve user interface
> - enhance data/time handling
> - improve taxonomy and classification
> - enhance ml pipeline
> - improve data source configuration
> - optimize database operations
> - enhance security and access control
> - improve event grouping
> - optimization of image processing
> - refactoring jobs and background tasks

Claude should output 2 csvs which can be combined into a single one. The output csvs should have heading This csv will have headings `["File", "Function", "Line Number", "Context", "Category", "Group"]`.
