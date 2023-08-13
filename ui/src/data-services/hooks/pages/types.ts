export interface Page {
  id: number
  name: string
  slug: string
}

export interface PageDetails extends Page {
  html: string
}
