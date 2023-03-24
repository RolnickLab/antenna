export type ServerSettings = any // TODO: Update this type
export type ServerSettingsField = any // TODO: Update this type
export type SettingsFieldType =
  | 'path'
  | 'string'
  | 'options'
  | 'numeric'
  | 'slider'

export class Settings {
  public readonly fields: { [id: string]: SettingsField }
  public readonly sections: { [id: string]: string[] }

  public constructor(data: ServerSettings) {
    const properties = Object.entries(data).map(
      ([id, fieldData]: [string, ServerSettingsField]) => ({
        id,
        ...fieldData,
      })
    )

    this.fields = properties.reduce((fields, fieldData) => {
      fields[fieldData.id] = new SettingsField(fieldData)
      return fields
    }, {})

    this.sections = properties.reduce((sections, fieldData) => {
      const sectionFields = sections[fieldData.section] ?? []
      sectionFields.push(fieldData.id)
      sections[fieldData.section] = sectionFields
      return sections
    }, {})
  }
}

export class SettingsField {
  private readonly _data: ServerSettingsField

  public constructor(data: ServerSettingsField) {
    this._data = data
  }

  get description(): string {
    return this._data.description
  }

  get id(): string {
    return this._data.id
  }

  get title(): string {
    return this._data.title
  }

  get type(): SettingsFieldType {
    return this._data.type
  }

  get options(): { value: string; label: string }[] | undefined {
    return this._data.options?.map((option: string) => ({
      value: option,
      label: option,
    }))
  }

  get settings():
    | {
        defaultValue: number
        min: number
        max: number
        step: number
      }
    | undefined {
    if (!this._data.settings) {
      return undefined
    }

    return {
      min: this._data.settings.minimum,
      max: this._data.settings.maximum,
      step: this._data.settings.step,
      defaultValue: this._data.settings.default,
    }
  }
}
