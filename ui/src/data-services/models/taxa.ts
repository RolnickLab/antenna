export type ServerTaxon = {
  id: string
  name: string
  rank: string
  parent?: ServerTaxon
  parents?: ServerTaxon[]
}

const SORTED_RANKS = [
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
    this.id = `${taxon.id}`
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

    // TODO: Perhaps sorting should happen backend side? If so, let's remove this later.
    this.ranks.sort((r1, r2) => {
      const value1 = SORTED_RANKS.indexOf(r1.rank)
      const value2 = SORTED_RANKS.indexOf(r2.rank)

      return value1 - value2
    })
  }

  get parents() {
    return this.ranks
  }
}
