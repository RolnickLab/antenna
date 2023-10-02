import { TreeItem } from './types'

export const sortTree = (tree: TreeItem[]): TreeItem[] =>
  tree
    .map((node) => ({
      ...node,
      children: sortTree([...node.children]),
    }))
    .sort((a, b) => a.label.localeCompare(b.label))
