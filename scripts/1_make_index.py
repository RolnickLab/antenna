# Walk through all files in the repo_path and output a csv file with all @TODO tags and their context
import argparse
import os
import re

import pandas as pd
import pathspec

parser = argparse.ArgumentParser()
parser.add_argument("--repo_path", type=str)
parser.add_argument("--output_file", default="make_index.csv", type=str)

# Define the number of lines before and after the TODO to include in context
CONTEXT_LINES = 5


def load_gitignore(repo_path):
    gitignore_path = os.path.join(repo_path, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, encoding="utf-8") as f:
            patterns = f.read().splitlines()
        return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, patterns)
    return None


def is_ignored(file_path, ignore_spec, repo_path):
    if ignore_spec:
        relative_path = os.path.relpath(file_path, repo_path)
        return ignore_spec.match_file(relative_path)
    return False


def find_todos_in_file(file_path):
    todos = []
    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines):
        if "@TODO" in line:
            # Find function name (if exists)
            func_name = find_function_name(lines, line_num)

            # Extract context
            start = max(0, line_num - CONTEXT_LINES)
            end = min(len(lines), line_num + CONTEXT_LINES + 1)
            context = "".join(lines[start:end])

            todos.append(
                {"File": file_path, "Function": func_name, "Line Number": line_num + 1, "Context": context.strip()}
            )
    return todos


def find_function_name(lines, line_num):
    # Look backwards for the most recent function definition (Python example)
    for i in range(line_num, -1, -1):
        line = lines[i].strip()
        # Adjust the regex for different languages as needed
        if re.match(r"def\s+\w+\(", line):  # Python function detection
            return line.split("(")[0].replace("def ", "")
    return "Unknown"


def search_repo_for_todos(repo_path, ignore_spec):
    todos = []
    # Walk through all files in the directory
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)

            if not file.endswith((".gz", ".lock")):  # Adjust to target other extensions if needed
                if not is_ignored(file_path, ignore_spec, repo_path):
                    print(f"Processing {file_path}")
                    todos.extend(find_todos_in_file(file_path))
                else:
                    print(f"Ignoring {file_path}")
            else:
                print(f"Skipping {file_path}")
    return todos


def write_todos_to_csv(todos, output_file):
    # Convert the todos list into a pandas DataFrame
    df = pd.DataFrame(todos, columns=["File", "Function", "Line Number", "Context"])

    # Write the DataFrame to a CSV file
    df.to_csv(output_file, index=False)


if __name__ == "__main__":
    args = parser.parse_args()

    repo_path = args.repo_path
    output_file = args.output_file

    # Load .gitignore
    ignore_spec = load_gitignore(repo_path)

    # Search for TODOs
    todos = search_repo_for_todos(repo_path, ignore_spec)

    # Write TODOs to CSV
    write_todos_to_csv(todos, output_file)

    print(f"TODO report generated: {output_file}")

# @TODO: check for \n in the context (readlines keeps them,
# read().splitlines() removes them)....maybe use read().splitlines()?
# but might need \n to maintain context

# @TODO: fix bug; sometimes TODO does not lie in a function, it lies in a class.
