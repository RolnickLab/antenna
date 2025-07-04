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
      ? classification.top_n
          .slice(0, 5)
          .filter(({ taxon }: any) => !!taxon)
          .map(({ logit, score, taxon }: any) => ({
            logit,
            score,
            taxon: new Taxon(taxon),
          }))
      : []
  }

  get id(): string {
    return `${this._classification.id}`
  }

  get logit(): number {
    return this._classification.logit
  }

  get score(): number {
    return this._classification.score
  }
}
