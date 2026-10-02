import { ServerJobType, ServerScopeField } from 'data-services/models/job-type'
import { buildJobPayload } from '../build-job-payload'

const scope = (
  field: string,
  overrides: Partial<ServerScopeField> = {}
): ServerScopeField => ({
  field,
  label: field,
  entity: 'x',
  required: true,
  ...overrides,
})

const mlType: ServerJobType = {
  key: 'ml',
  name: 'ML pipeline',
  allowed: true,
  scope: [scope('pipeline_id'), scope('source_image_collection_id')],
  required_fields: [],
  required_params: [],
  config_schema: null,
  variant_key: null,
  variants: [],
}

const postProcessing: ServerJobType = {
  ...mlType,
  key: 'post_processing',
  name: 'Post Processing',
  scope: [],
  variant_key: 'task',
  variants: [
    {
      key: 'class_masking',
      name: 'Class masking',
      config_schema: {
        required: ['taxa_list_id'],
        properties: {
          source_image_collection_id: {
            type: 'integer',
            ami_widget: 'entity',
            ami_entity: 'captures/collections',
          },
          occurrence_id: { type: 'integer', ami_widget: 'hidden' },
          taxa_list_id: {
            type: 'integer',
            ami_widget: 'entity',
            ami_entity: 'taxa/lists',
          },
          reweight: { type: 'boolean', default: true },
          note: { type: 'string' },
        },
      },
    },
  ],
}

describe('buildJobPayload', () => {
  test('ml job puts scope fields at the top level and omits params', () => {
    const { body, startNow } = buildJobPayload({
      projectId: '7',
      jobType: mlType,
      scopeValues: { pipeline_id: '3', source_image_collection_id: '12' },
      scopeLabels: { source_image_collection_id: 'Night 1' },
      configValues: {},
      name: 'My job',
      delay: '5',
      startNow: true,
    })
    expect(body).toEqual({
      name: 'My job',
      delay: 5,
      project_id: '7',
      job_type_key: 'ml',
      pipeline_id: 3,
      source_image_collection_id: 12,
    })
    expect(startNow).toBe(true)
  })

  test('post processing nests the method and its settings, hidden fields left out', () => {
    const { body } = buildJobPayload({
      projectId: '7',
      jobType: postProcessing,
      variant: postProcessing.variants[0],
      scopeValues: {},
      configValues: {
        source_image_collection_id: '12',
        occurrence_id: '9',
        taxa_list_id: '4',
        reweight: true,
        note: '',
      },
    })
    expect(body.params).toEqual({
      task: 'class_masking',
      config: {
        taxa_list_id: 4,
        reweight: true,
        source_image_collection_id: 12,
      },
    })
    expect(body).not.toHaveProperty('source_image_collection_id')
  })

  test('defaults: name from method and scope label, delay 0, no start', () => {
    const { body, startNow } = buildJobPayload({
      projectId: '7',
      jobType: postProcessing,
      variant: postProcessing.variants[0],
      scopeValues: {},
      scopeLabels: { source_image_collection_id: 'Night 1' },
      configValues: {},
    })
    expect(body.name).toBe('Class masking – Night 1')
    expect(body.delay).toBe(0)
    expect(startNow).toBe(false)
  })

  test('name falls back to the date without a scope label', () => {
    const { body } = buildJobPayload({
      projectId: '7',
      jobType: mlType,
      scopeValues: {},
      configValues: {},
      name: '  ',
      today: '2026-09-30',
    })
    expect(body.name).toBe('ML pipeline – 2026-09-30')
  })

  test('own config schema wraps config; empty optional values are omitted', () => {
    const type: ServerJobType = {
      ...mlType,
      scope: [],
      config_schema: {
        properties: {
          size: { type: 'number' },
          ids: { type: 'array', items: { type: 'integer' } },
        },
      },
    }
    const { body } = buildJobPayload({
      projectId: '1',
      jobType: type,
      scopeValues: {},
      configValues: { size: '', ids: '1, 2' },
    })
    expect(body.params).toEqual({ config: { ids: [1, 2] } })
  })
})
