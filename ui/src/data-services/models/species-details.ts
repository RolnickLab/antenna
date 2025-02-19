import { ServerSpecies, Species } from './species'

export type ServerSpeciesDetails = ServerSpecies & any // TODO: Update this type

export class SpeciesDetails extends Species {
  public constructor(species: ServerSpeciesDetails) {
    super(species)
  }
}
