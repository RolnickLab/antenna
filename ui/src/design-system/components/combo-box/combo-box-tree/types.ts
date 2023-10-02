export type Node = {
  id: string
  label: string
  parentId?: string
}

export type TreeItem = Node & { children: TreeItem[] }
