/** The items either side of the current one, or undefined at an end or when it is not listed. */
export const getAdjacentIds = (
  items: { id: string }[] | undefined,
  currentId: string | undefined
): { prevId?: string; nextId?: string } => {
  const index = items?.findIndex((item) => item.id === currentId) ?? -1
  if (!items || index < 0) {
    return {}
  }

  return { prevId: items[index - 1]?.id, nextId: items[index + 1]?.id }
}
