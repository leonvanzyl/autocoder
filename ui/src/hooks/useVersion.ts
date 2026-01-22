import { useQuery } from '@tanstack/react-query'
import { getBackendVersion } from '../lib/api'

export function useBackendVersion() {
  return useQuery({
    queryKey: ['backend-version'],
    queryFn: getBackendVersion,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}

