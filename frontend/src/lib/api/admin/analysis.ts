import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client'; // Import the singleton instance
import { useToast } from '@/hooks/use-toast';

// Define AnalysisStatus as both a type and an enum-like object (from types.ts)
export type AnalysisStatus = "pending" | "in_progress" | "completed" | "failed";

export const AnalysisStatus = {
  PENDING: "pending" as AnalysisStatus,
  IN_PROGRESS: "in_progress" as AnalysisStatus,
  COMPLETED: "completed" as AnalysisStatus,
  FAILED: "failed" as AnalysisStatus,
};

/**
 * Overall analysis status summary.
 */
export interface AnalysisStatusSummary {
  total: number;
  completed: number;
  pending: number;
  failed: number;
  in_progress: number;
  max_retries_reached: number;
  can_process?: boolean;
}

/**
 * Simple response for job operations.
 */
export interface SimpleJobResponse {
  message: string;
  job_id: string;
}

/**
 * Schema for analyzed listings (as received by frontend).
 */
export interface AnalyzedListingDocument {
  _id?: string | null; // Beanie/Mongo ID
  original_listing_id: string;
  type?: string | null;
  brand?: string | null;
  base_model?: string | null;
  model_variant?: string | null;
  info?: Record<string, any>; // Changed from unknown
  embeddings?: number[] | null;
  analysis_version?: string;
  retry_count?: number;
}

// AnalyzedListing type alias (from types.ts)
export type AnalyzedListing = AnalyzedListingDocument;

// Define the base path for analysis admin routes
const ANALYSIS_BASE_PATH = '/admin/analysis';
const ANALYSIS_QUERY_KEY_PREFIX = 'analysis';

// --- Query Hooks ---

export function useAnalysisStatus() {
  return useQuery<AnalysisStatusSummary, Error>({
    queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'status'],
    queryFn: () => apiClient._fetch(`${ANALYSIS_BASE_PATH}/status`),
  });
}

export function useListingAnalysisByOriginalId(originalId: string | null | undefined) {
  return useQuery<AnalyzedListingDocument, Error>({
    queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'listing', originalId],
    queryFn: () => {
      if (!originalId) return Promise.reject(new Error("originalId is required"));
      return apiClient._fetch(`${ANALYSIS_BASE_PATH}/by-original-id/${originalId}`);
    },
    enabled: !!originalId, // Only run query if originalId is present
  });
}


// --- Mutation Hooks ---

export function useStartAnalysisMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, void>({ // void for no variables
    mutationFn: () => apiClient._fetch(`${ANALYSIS_BASE_PATH}/start`, { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'status'] });
      toast({ title: "Success", description: data.message || "Analysis started." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to start analysis." });
    },
  });
}

export function useRetryFailedAnalysesMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, void>({
    mutationFn: () => apiClient._fetch(`${ANALYSIS_BASE_PATH}/retry-failed`, { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'status'] });
      toast({ title: "Success", description: data.message || "Retrying failed analyses." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to retry analyses." });
    },
  });
}

export function useResumeAnalysisMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, void>({
    mutationFn: () => apiClient._fetch(`${ANALYSIS_BASE_PATH}/resume`, { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'status'] });
      toast({ title: "Success", description: data.message || "Analysis resumed." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to resume analysis." });
    },
  });
}

export function useCancelAnalysisMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, void>({
    mutationFn: () => apiClient._fetch(`${ANALYSIS_BASE_PATH}/cancel`, { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'status'] });
      toast({ title: "Success", description: data.message || "Analysis cancelled." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to cancel analysis." });
    },
  });
}

export function useRegenerateEmbeddingsMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<SimpleJobResponse, Error, void>({
    mutationFn: () => apiClient._fetch(`${ANALYSIS_BASE_PATH}/regenerate-embeddings`, { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'status'] });
      queryClient.invalidateQueries({ queryKey: [ANALYSIS_QUERY_KEY_PREFIX, 'listing'] }); // Invalidate all individual listing analyses
      toast({ title: "Success", description: data.message || "Embeddings regeneration started." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to regenerate embeddings." });
    },
  });
}