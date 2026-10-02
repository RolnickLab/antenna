import {
  getInitialValue,
  schemaToFields,
  scopeToFields,
  validateNumber,
} from '../schema-to-fields'

const schema = {
  required: ['taxa_list_id'],
  properties: {
    taxa_list_id: {
      title: 'Taxa list to keep',
      description: 'Help',
      type: 'integer',
      ami_widget: 'entity',
      ami_entity: 'taxa/lists',
    },
    algorithm_id: {
      type: 'integer',
      ami_widget: 'entity',
      ami_entity: 'ml/algorithms',
      ami_entity_filters: { task_type: 'classification' },
    },
    reweight: { type: 'boolean', default: true },
    size_threshold: {
      type: 'number',
      default: 0.0008,
      exclusiveMinimum: 0,
      exclusiveMaximum: 1,
    },
    count: { type: 'integer', minimum: 1, maximum: 5 },
    mode: { type: 'string', enum: ['a', 'b'] },
    note: { type: 'string' },
    ids: { type: 'array', items: { type: 'integer' } },
    other: { type: 'object' },
  },
}

describe('schemaToFields', () => {
  const fields = Object.fromEntries(
    schemaToFields(schema).map((f) => [f.name, f])
  )

  test('maps entity widgets with route, filters and required flag', () => {
    expect(fields.taxa_list_id).toMatchObject({
      kind: 'entity',
      entity: 'taxa/lists',
      required: true,
      label: 'Taxa list to keep',
      description: 'Help',
    })
    expect(fields.algorithm_id.entityFilters).toEqual({
      task_type: 'classification',
    })
    expect(fields.algorithm_id.label).toBe('algorithm_id')
    expect(fields.algorithm_id.required).toBe(false)
  })

  test('maps primitives and bounds', () => {
    expect(fields.reweight).toMatchObject({
      kind: 'boolean',
      defaultValue: true,
    })
    expect(fields.size_threshold).toMatchObject({
      kind: 'number',
      exclusiveMin: 0,
      exclusiveMax: 1,
    })
    expect(fields.count).toMatchObject({ kind: 'integer', min: 1, max: 5 })
    expect(fields.mode).toMatchObject({ kind: 'select', options: ['a', 'b'] })
    expect(fields.note.kind).toBe('text')
    expect(fields.ids.kind).toBe('integer-list')
    expect(fields.other.kind).toBe('json')
  })

  test('returns no fields for a missing schema', () => {
    expect(schemaToFields(null)).toEqual([])
    expect(schemaToFields({ properties: {} })).toEqual([])
  })
})

describe('scopeToFields', () => {
  test('a job column becomes a required entity picker', () => {
    const [field] = scopeToFields([
      {
        field: 'deployment_id',
        label: 'Station',
        entity: 'deployments',
        required: true,
      },
    ])
    expect(field).toMatchObject({
      kind: 'entity',
      required: true,
      entity: 'deployments',
    })
  })
})

describe('getInitialValue / validateNumber', () => {
  test('defaults are stringified except booleans', () => {
    const [reweight, threshold, count] = schemaToFields(schema).filter((f) =>
      ['reweight', 'size_threshold', 'count'].includes(f.name)
    )
    expect(getInitialValue(reweight)).toBe(true)
    expect(getInitialValue(threshold)).toBe('0.0008')
    expect(getInitialValue(count)).toBeUndefined()
  })

  test('validates bounds and integers', () => {
    const f = Object.fromEntries(schemaToFields(schema).map((x) => [x.name, x]))
    expect(validateNumber(f.size_threshold, '0')).toBeDefined()
    expect(validateNumber(f.size_threshold, '1')).toBeDefined()
    expect(validateNumber(f.size_threshold, '0.5')).toBeUndefined()
    expect(validateNumber(f.count, '0')).toBeDefined()
    expect(validateNumber(f.count, '6')).toBeDefined()
    expect(validateNumber(f.count, '2.5')).toBeDefined()
    expect(validateNumber(f.count, '')).toBeUndefined()
  })
})

describe('empty defaults, hidden and advanced settings', () => {
  const fields = schemaToFields({
    type: 'object',
    properties: {
      steps: { title: 'Activity steps', type: 'array', default: [] },
      floor: { title: 'Floor', type: 'number' },
      gate: {
        title: 'Gate',
        type: 'string',
        default: 'off',
        ami_advanced: true,
      },
    },
    required: [],
  } as any)

  it('starts empty list and object defaults blank instead of as raw JSON', () => {
    expect(getInitialValue(fields[0])).toBeUndefined()
    expect(getInitialValue(fields[1])).toBeUndefined()
    expect(getInitialValue(fields[2])).toBe('off')
  })

  it('carries the advanced hint', () => {
    expect(fields.map((f) => !!f.advanced)).toEqual([false, false, true])
  })

  it('leaves hidden fields out, and an id list with a picker hint stays a list', () => {
    const [ids] = schemaToFields({
      properties: {
        occurrence_id: { type: 'integer', ami_widget: 'hidden' },
        event_ids: {
          type: 'array',
          items: { type: 'integer' },
          ami_widget: 'entity',
          ami_entity: 'events',
        },
      },
    })
    expect(ids).toMatchObject({ name: 'event_ids', kind: 'integer-list' })
  })
})
