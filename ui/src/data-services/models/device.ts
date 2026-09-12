import { Entity, ServerEntity } from './entity'

export class Device extends Entity {
  public constructor(entity: ServerEntity) {
    super(entity)
  }

  /* Free-form metadata object, empty when the device type has none. */
  get metadata(): object {
    return this._data.metadata ?? {}
  }
}
