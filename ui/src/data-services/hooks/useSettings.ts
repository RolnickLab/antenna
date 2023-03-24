import { Settings } from 'data-services/models/settings'
import data from '../example-data/settings.json'

export const useSettings = () => {
  // TODO: Use real data

  return new Settings(data)
}
