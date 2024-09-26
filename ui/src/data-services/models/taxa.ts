export type ServerTaxon = {
  id: string
  name: string
  rank: string
  parent?: ServerTaxon
  parents?: ServerTaxon[]
}

export const SORTED_RANKS = [
  'Unknown',
  'ORDER',
  'SUBORDER',
  'SUPERFAMILY',
  'FAMILY',
  'SUBFAMILY',
  'TRIBE',
  'SUBTRIBE',
  'GENUS',
  'SPECIES',
  'SUBSPECIES',
]
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
    } else {
      this.ranks = []
    }

    // TODO: Perhaps sorting should happen backend side? If so, let's remove this later.
    this.ranks.sort((r1, r2) => {
      const value1 = SORTED_RANKS.indexOf(r1.rank)
      const value2 = SORTED_RANKS.indexOf(r2.rank)

      return value1 - value2
    })
  }
}
