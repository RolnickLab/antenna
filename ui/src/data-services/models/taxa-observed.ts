import { ServerTaxon, Taxon } from './taxa'

export type ServerTaxonObserved = {
  id: string
  taxon: ServerTaxon
  detections_count: number
  occurrences_count: number
  best_determinations_score: number
  occurrence_images: string[]
  last_detected: string
}

export class TaxonObserved {
  readonly id: string
  readonly taxon: Taxon

  public constructor(taxonObserved: ServerTaxonObserved) {
    this.id = taxonObserved.id
    this.taxon = new Taxon(taxonObserved.taxon)
  }
}
