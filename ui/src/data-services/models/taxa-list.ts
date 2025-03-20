import { Entity, ServerEntity } from 'data-services/models/entity'

export type ServerTaxaList = ServerEntity & {
  taxa: string // URL to taxa API endpoint (filtered by this TaxaList)
  projects: number[] // Array of project IDs
}

export class TaxaList extends Entity {
  protected readonly _taxaList: ServerTaxaList

  public constructor(taxaList: ServerTaxaList) {
    super(taxaList) // Call the parent class constructor
    this._taxaList = taxaList
  }

  get taxaUrl(): string {
    return this._taxaList.taxa
  }


}
