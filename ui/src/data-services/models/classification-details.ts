import _ from 'lodash'
import { Algorithm } from './algorithm'
import { Taxon } from './taxa'

export type ServerClassificationDetails = any // TODO: Update this type

export class ClassificationDetails {
  protected readonly _classification: ServerClassificationDetails

  public readonly algorithm: Algorithm
  public readonly taxon: Taxon
  public readonly topN: {
    logit: number
    score: number
    taxon: Taxon
  }[]

  public constructor(classification: ServerClassificationDetails) {
    this._classification = classification
    this.algorithm = new Algorithm(classification.algorithm)
    this.taxon = new Taxon(classification.taxon)
    this.topN = classification.top_n
      .filter(({ taxon }: any) => !!taxon)
      .map(({ logit, score, taxon }: any) => ({
        logit: _.round(logit, 4),
        score: _.round(score, 4),
        taxon: new Taxon(taxon),
      }))
  }

  get id(): string {
    return `${this._classification.id}`
  }

  get logit(): number {
    return _.round(this._classification.logit, 4)
  }

  get score(): number {
    return _.round(this._classification.score, 4)
  }
}
