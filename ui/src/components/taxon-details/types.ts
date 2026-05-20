export interface Taxon {
  id: string;
  name: string;
  parents: { id: string; name: string; rank: string }[];
  rank: string;
}
