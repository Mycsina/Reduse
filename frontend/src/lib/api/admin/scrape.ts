import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

const basePath = '/admin/scrape'; // Define base path locally
const SCRAPE_QUERY_KEY_PREFIX = 'scrape'; // For potential future queries or related invalidations

/**
 * Response model for endpoints that start a background task.
 */
export interface QueuedTaskResponse {
  message: string;
  queue_id: string;
}

// --- Mutation Hooks ---

export function useScrapeUrlMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<QueuedTaskResponse, Error, string>({ // string for URL variable
    mutationFn: (url: string) => apiClient._fetch(`${basePath}/url-with-analysis/`, { method: 'POST', body: JSON.stringify({ url }) }),
    onSuccess: (data) => {
      toast({ title: "Success", description: data.message || "URL scraping started." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to start URL scraping." });
    },
  });
}