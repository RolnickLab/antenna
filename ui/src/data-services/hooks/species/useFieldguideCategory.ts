import { useQuery } from '@tanstack/react-query'

const ROOT_CATEGORY = '5926f024fd89783b2a721ba8' // Lepidoptera

const API_URL = '/fieldguide/api2'

const QUERY_KEY = 'fieldguide-category'

interface FieldguideCategory {
  id: string
  common_name: string
  cover_image: {
    photo_id: string
    base_image_url: string
    image_url: string
    width: number
    height: number
    copyright: string
  }
}

export const useFieldguideCategory = (q: string) => {
  const { isLoading, error, data } = useQuery<FieldguideCategory>({
    queryKey: [QUERY_KEY, q],
    queryFn: async () => {
      // Search categories by string
      const categoriesRes = await fetch(
        `${API_URL}/search/search?category=${ROOT_CATEGORY}&keywords=${q}&limit=1`
      )

      const categories = await categoriesRes.json()
      const categoryId = categories.filter(
        (category: any) => category.object_type === 'category'
      )[0]?.id

      // Throw error if no match
      if (!categoryId) {
        throw Error()
      }

      // Fetch category details by id
      const categoryRes = await fetch(
        `${API_URL}/categories/category_details?category_id=${categoryId}`
      )
      const category = await categoryRes.json()

      return category
    },
    retry: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
    staleTime: Infinity,
  })

  return { isLoading, error, category: data }
}
