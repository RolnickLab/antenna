import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'

export type ServerAlgorithm = any // TODO: Update this type

export class Algorithm {
  protected readonly _algorithm: ServerAlgorithm

  public constructor(algorithm: ServerAlgorithm) {
    this._algorithm = algorithm
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._algorithm.created_at),
    })
  }

  get description(): string | undefined {
    return this._algorithm.description
  }

  get id(): string {
    return `${this._algorithm.id}`
  }

  get name(): string {
    return this._algorithm.name
  }

  get key(): string {
    return this._algorithm.key
  }

  get uri(): string {
    return this._algorithm.uri
  }

  get updatedAt(): string | undefined {
    if (!this._algorithm.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._algorithm.updated_at),
    })
  }
}
