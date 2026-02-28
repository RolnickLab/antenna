import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'

export type ServerEntity = any // TODO: Update this type

export class Entity {
  protected readonly _data: ServerEntity

  public constructor(entity: ServerEntity) {
    this._data = entity
  }

  get canUpdate(): boolean {
    return this._data.user_permissions?.includes(UserPermission.Update)
  }

  get canDelete(): boolean {
    return this._data.user_permissions?.includes(UserPermission.Delete)
  }

  get createdAt(): string | undefined {
    if (!this._data.created_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._data.created_at),
    })
  }

  get description(): string | undefined {
    return this._data.description
  }

  get id(): string {
    return `${this._data.id}`
  }

  get name(): string {
    return this._data.name
  }

  get updatedAt(): string | undefined {
    if (!this._data.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._data.updated_at),
    })
  }

  get updatedAtDetailed(): string | undefined {
    if (!this._data.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._data.updated_at),
      options: { second: true },
    })
  }
}
