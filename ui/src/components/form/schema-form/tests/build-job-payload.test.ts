import { ServerJobType } from 'data-services/models/job-type'
import { buildJobPayload } from '../build-job-payload'

const mlType: ServerJobType = {
  key: 'ml',
  name: 'Process captures',
  group: 'process_images',
  allowed: true,
  config_schema: {
    required: ['pipeline_id'],
    properties: {
      pipeline_id: {
        type: 'integer',
        ami_widget: 'entity',
        ami_entity: 'ml/pipelines',
      },
      source_image_collection_id: {
        type: 'integer',
        ami_widget: 'entity',
        ami_entity: 'captures/collections',
      },
    },
  },
  variant_key: null,
  variants: [],
}

const postProcessing: ServerJobType = {
  ...mlType,
  key: 'post_processing',
  name: 'Post Processing',
  group: null,
  config_schema: null,
  variant_key: 'task',
  variants: [
    {
      key: 'class_masking',
      name: 'Limit predictions to a species list',
      group: 'refine_results',
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
  test('ml job sends its pipeline and capture set in params', () => {
    const { body, startNow } = buildJobPayload({
      projectId: '7',
      jobType: mlType,
      pickedLabels: { source_image_collection_id: 'Night 1' },
      configValues: { pipeline_id: '3', source_image_collection_id: '12' },
      name: 'My job',
      delay: '5',
      startNow: true,
    })
    expect(body).toEqual({
      name: 'My job',
      delay: 5,
      project_id: '7',
      job_type_key: 'ml',
      params: { config: { pipeline_id: 3, source_image_collection_id: 12 } },
    })
    expect(startNow).toBe(true)
  })

  test('post processing nests the method and its settings, hidden fields left out', () => {
    const { body } = buildJobPayload({
      projectId: '7',
      jobType: postProcessing,
      variant: postProcessing.variants[0],
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

  test('defaults: name from method and picked label, delay 0, no start', () => {
    const { body, startNow } = buildJobPayload({
      projectId: '7',
      jobType: postProcessing,
      variant: postProcessing.variants[0],
      pickedLabels: { source_image_collection_id: 'Night 1' },
      configValues: {},
    })
    expect(body.name).toBe('Limit predictions to a species list – Night 1')
    expect(body.delay).toBe(0)
    expect(startNow).toBe(false)
  })

  test('name prefers the capture set over other picked labels', () => {
    const { body } = buildJobPayload({
      projectId: '7',
      jobType: mlType,
      pickedLabels: {
        pipeline_id: 'Moths',
        source_image_collection_id: 'Night 1',
      },
      configValues: {},
    })
    expect(body.name).toBe('Process captures – Night 1')
  })

  test('name falls back to the date without a picked label', () => {
    const { body } = buildJobPayload({
      projectId: '7',
      jobType: mlType,
      configValues: {},
      name: '  ',
      today: '2026-09-30',
    })
    expect(body.name).toBe('Process captures – 2026-09-30')
  })

  test('own config schema wraps config; empty optional values are omitted', () => {
    const type: ServerJobType = {
      ...mlType,
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
      configValues: { size: '', ids: '1, 2' },
    })
    expect(body.params).toEqual({ config: { ids: [1, 2] } })
  })
})
