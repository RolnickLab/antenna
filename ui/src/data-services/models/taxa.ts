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

    if (taxon.parents) {
      this.ranks = taxon.parents
    } else if (taxon.parent?.parents) {
      // TODO: Update this when species list is returning parents similar to other endpoints
      this.ranks = [taxon.parent, ...taxon.parent.parents]
    } else {
      this.ranks = []
    }
  }
}
