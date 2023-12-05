import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'

export type ServerEntity = any // TODO: Update this type

export class Entity {
  protected readonly _entity: ServerEntity

  public constructor(entity: ServerEntity) {
    this._entity = entity
  }

  get canDelete(): boolean {
    return this._entity.user_permissions.includes(UserPermission.Delete)
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._entity.created_at),
    })
  }

  get description(): string {
    return this._entity.description
  }

  get id(): string {
    return `${this._entity.id}`
  }

  get name(): string {
    return this._entity.name
  }

  get updatedAt(): string | undefined {
    if (!this._entity.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._entity.updated_at),
    })
  }
}
