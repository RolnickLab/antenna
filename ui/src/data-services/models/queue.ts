import { STRING, translate } from 'utils/language'

export type ServerQueue = any // TODO: Update this type

export class Queue {
  private readonly _queue: ServerQueue

  public constructor(batchId: ServerQueue) {
    this._queue = batchId
  }

  get complete(): number {
    return this._queue.complete
  }

  get description(): string {
    return this._queue.description
  }

  get id(): string {
    return this._queue.id
  }

  get queued(): number {
    return this._queue.complete
  }

  get statusLabel(): string {
    switch (this._queue.status) {
      case 'running':
        return translate(STRING.RUNNING)
      case 'stopped':
        return translate(STRING.STOPPED)
      default:
        return ''
    }
  }

  get unprocessed(): number {
    return this._queue.unprocessed
  }
}
