export type Node = {
  id: string
  label: string
  details: string
  parentId?: string
}

export type TreeItem = Node & { children: TreeItem[] }
