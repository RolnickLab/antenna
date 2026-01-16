import { Entity, ServerEntity } from 'data-services/models/entity'

export type ServerTaxaList = ServerEntity & {
  projects: number[] // Array of project IDs
  taxa: string // URL to taxa API endpoint (filtered by this taxa list)
  taxa_count: number // Number of taxa in list
}

export class TaxaList extends Entity {
  protected readonly _taxaList: ServerTaxaList

  public constructor(taxaList: ServerTaxaList) {
    super(taxaList)

    this._taxaList = taxaList
  }

  get taxaCount() {
    return this._taxaList.taxa_count
  }
}
