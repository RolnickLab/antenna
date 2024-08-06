export type ServerTaxon = {
  id: string
  name: string
  rank: string
  parent?: ServerTaxon
  parents?: ServerTaxon[]
}

export class Taxon {
  readonly id: string
  readonly name: string
  readonly parentId?: string
  readonly rank: string
  readonly ranks: { id: string; name: string; rank: string }[]

  public constructor(taxon: ServerTaxon) {
    this.id = taxon.id
    this.name = taxon.name
    this.parentId = taxon.parent ? `${taxon.parent?.id}` : undefined
    this.rank = taxon.rank
    this.ranks = taxon.parents ? taxon.parents : []
  }
}
