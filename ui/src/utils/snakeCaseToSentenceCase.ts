import _ from 'lodash'

export const snakeCaseToSentenceCase = (input: string) =>
  _.capitalize(input.split('_').join(' '))
