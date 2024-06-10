import { Node, TreeItem } from './types'

export const buildTree = (data: Node[]) => {
  const tree: TreeItem[] = []
  const treeMap: { [key: string]: TreeItem } = {}

  data.forEach((node: Node) => (treeMap[node.id] = { ...node, children: [] }))

  data.forEach((node: Node) => {
    if (node.parentId && treeMap[node.parentId]) {
      treeMap[node.parentId].children.push(treeMap[node.id])
    } else {
      tree.push(treeMap[node.id])
    }
  })

  return tree
}
