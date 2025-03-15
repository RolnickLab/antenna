import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { UserPermission } from 'utils/user/types'

export type ServerTaxaList = {
  id: number
  name: string
  description?: string
  taxa: string // URL to taxa API endpoint (filtered by this TaxaList)
  projects: number[] // Array of project IDs
  created_at?: string
  user_permissions?: UserPermission[]
}

export class TaxaList {
  protected readonly _taxaList: ServerTaxaList

  public constructor(taxaList: ServerTaxaList) {
    this._taxaList = taxaList
  }

  get id(): string {
    return `${this._taxaList.id}`
  }

  get name(): string {
    return this._taxaList.name
  }

  get description(): string | undefined {
    return this._taxaList.description || undefined
  }

  get taxaUrl(): string {
    return this._taxaList.taxa
  }

  get projectIds(): number[] {
    return this._taxaList.projects
  }

  get createdAt(): Date | undefined {
    return this._taxaList.created_at
      ? new Date(this._taxaList.created_at)
      : undefined
  }

  get createdAtLabel(): string | undefined {
    return this.createdAt
      ? getFormatedDateString({ date: this.createdAt })
      : undefined
  }

  get canDelete(): boolean {
    return this._taxaList.user_permissions?.includes(UserPermission.Delete) ?? false
  }

  get canUpdate(): boolean {
    return this._taxaList.user_permissions?.includes(UserPermission.Update) ?? false
  }
}
