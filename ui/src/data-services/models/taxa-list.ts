import { Entity, ServerEntity } from 'data-services/models/entity'

export type ServerTaxaListBestModel = {
  id: number
  name: string
  accuracy: number | null
  accuracy_by_species: number | null
  occurrence_set: string
}

export interface TaxaListBestModel {
  id: string
  name: string
  accuracyBySpecies?: number
  occurrenceSetName: string
}

export type ServerTaxaList = ServerEntity & {
  best_model: ServerTaxaListBestModel | null // Highest scoring algorithm on these taxa
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

  get bestModel(): TaxaListBestModel | undefined {
    const model = this._taxaList.best_model

    if (!model) {
      return undefined
    }

    return {
      id: `${model.id}`,
      name: model.name,
      accuracyBySpecies: model.accuracy_by_species ?? undefined,
      occurrenceSetName: model.occurrence_set,
    }
  }

  get taxaCount() {
    return this._taxaList.taxa_count
  }
}
