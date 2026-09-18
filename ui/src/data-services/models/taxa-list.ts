import { Entity, ServerEntity } from 'data-services/models/entity'

// Summary of an algorithm whose category map a managed taxa list mirrors.
// The API includes more read-only fields (version, timestamps, etc.); only
// the ones this UI links to or displays are typed here.
export type ServerTaxaListAlgorithm = {
  id: number
  name: string
  key: string
}

export type ServerTaxaList = ServerEntity & {
  projects: number[] // Array of project IDs
  taxa: string // URL to taxa API endpoint (filtered by this taxa list)
  taxa_count: number // Number of taxa in list
  is_public: boolean
  algorithms: ServerTaxaListAlgorithm[]
  copied_from?: { id: number; name: string } | null
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

  get isPublic(): boolean {
    return this._taxaList.is_public
  }

  // A managed list mirrors a classifier's category map: its membership is
  // fixed for everyone and can only be changed by copying it. Derived from
  // `algorithms` rather than a server-sent flag, since the flag is redundant
  // with it and may be removed. See #1420.
  get isManaged(): boolean {
    return this._taxaList.algorithms.length > 0
  }

  get algorithms(): ServerTaxaListAlgorithm[] {
    return this._taxaList.algorithms
  }

  get copiedFrom(): { id: string; name: string } | undefined {
    return this._taxaList.copied_from
      ? {
          id: `${this._taxaList.copied_from.id}`,
          name: this._taxaList.copied_from.name,
        }
      : undefined
  }
}
