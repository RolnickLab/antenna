const WINDOW_SIZE = 2

export const getPageWindow = (currentPage: number, numPages: number) => {
  const pages = Array.from(Array(numPages).keys())
  const startIndex = currentPage - WINDOW_SIZE
  const endIndex = currentPage + WINDOW_SIZE + 1

  const offset = (() => {
    if (startIndex < 0) {
      return -startIndex
    }
    if (endIndex >= pages.length) {
      return pages.length - endIndex
    }
    return 0
  })()

  return pages.slice(startIndex + offset, endIndex + offset)
}
