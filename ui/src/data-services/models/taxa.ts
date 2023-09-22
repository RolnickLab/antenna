export type ServerTaxon = {
  id: number
  name: string
  rank: string
  parent?: ServerTaxon
}

export class Taxon {
  readonly id: string
  readonly name: string
  readonly rank: string
  readonly ranks: { id: string; name: string; rank: string }[]

  public constructor(taxon: ServerTaxon) {
    this.id = `${taxon.id}`
    this.name = taxon.name
    this.rank = taxon.rank
    this.ranks = this.getRanks(taxon)
  }

  private getRanks(taxon: ServerTaxon) {
    const ranks = []

    let current: ServerTaxon | undefined = taxon.parent
    while (current) {
      ranks.push({
        id: `${current.id}`,
        name: current.name,
        rank: current.rank,
      })
      current = current.parent
    }

    return ranks.reverse()
  }
}
