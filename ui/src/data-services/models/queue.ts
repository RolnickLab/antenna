import { STRING, translate } from 'utils/language'

export type ServerQueue = any // TODO: Update this type

export class Queue {
  private readonly _queue: ServerQueue

  public constructor(queue: ServerQueue) {
    this._queue = queue
  }

  get complete(): number {
    return this._queue.done_count
  }

  get description(): string {
    return this._queue.name
  }

  get id(): string {
    return this._queue.name
  }

  get queued(): number {
    return this._queue.queue_count
  }

  get statusLabel(): string {
    return 'WIP'

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
    return this._queue.unprocessed_count
  }
}
