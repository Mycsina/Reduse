import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

const basePath = '/analytics';
const priceStatsPath = '/price-stats';
export const PRICE_STATS_QUERY_KEY_PREFIX = 'priceStats';

/**
 * Document for storing model price statistics.
 */

export interface ModelPriceStats {
  _id?: string | null; // Beanie/Mongo ID
  base_model: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  median_price: number;
  sample_size: number;
  timestamp: string;
  variants?: string[];
}

export interface ModelAnalytics {
  model: string;
  count: number;
  avgPrice: number;
  minPrice: number;
  maxPrice: number;
  medianPrice?: number;
  sampleSize?: number;
  timestamp?: string;
}

// --- Query Hooks ---

export function useCurrentModelStats(baseModel: string | null | undefined) {
  return useQuery<ModelPriceStats | null, Error>({
    queryKey: [PRICE_STATS_QUERY_KEY_PREFIX, 'current', baseModel],
    queryFn: () => {
      if (!baseModel) return Promise.resolve(null);
      return apiClient._fetch(`${basePath}${priceStatsPath}/current/${baseModel}`);
    },
    enabled: !!baseModel,
  });
}

export function useModelPriceHistory(
  baseModel: string | null | undefined,
  days: number = 30,
  limit?: number
) {
  return useQuery<ModelPriceStats[], Error>({
    queryKey: [PRICE_STATS_QUERY_KEY_PREFIX, 'history', baseModel, { days, limit }],
    queryFn: () => {
      if (!baseModel) return Promise.resolve([]); // Handle null/undefined baseModel gracefully
      const params = new URLSearchParams();
      if (days) params.append('days', days.toString());
      if (limit) params.append('limit', limit.toString());
      return apiClient._fetch(`${basePath}${priceStatsPath}/history/${baseModel}?${params}`);
    },
    enabled: !!baseModel,
  });
}

// --- Original API functions to be mixed into apiClient ---

export interface UpdatePriceStatsResponse {
  message: string;
}

export function useUpdatePriceStatsMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<UpdatePriceStatsResponse, Error, void>({ 
    mutationFn: () => apiClient._fetch(`${basePath}${priceStatsPath}/trigger-update`, {
      method: 'POST',
    }),
    onSuccess: (data) => {
      toast({ title: "Success", description: data.message || "Price statistics update triggered." });
      queryClient.invalidateQueries({ queryKey: [PRICE_STATS_QUERY_KEY_PREFIX, 'current'] });
      queryClient.invalidateQueries({ queryKey: [PRICE_STATS_QUERY_KEY_PREFIX, 'history'] });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to trigger price statistics update." });
    },
  });
}

// --- Server-callable data fetching functions ---
export async function fetchCurrentModelStats(baseModel: string): Promise<ModelPriceStats | null> {
  if (!baseModel) return Promise.resolve(null);
  return apiClient._fetch(`${basePath}${priceStatsPath}/current/${baseModel}`);
}