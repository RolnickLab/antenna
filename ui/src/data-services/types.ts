export interface FetchSettings {
  pagination?: { page: number; perPage: number }
  sort?: { field: string; order: 'asc' | 'desc' }
}
