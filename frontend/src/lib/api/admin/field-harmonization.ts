import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

// Import query keys for invalidation
import { QUERY_API_QUERY_KEY_PREFIX } from '@/lib/api/query/query';
import { PRICE_STATS_QUERY_KEY_PREFIX } from '@/lib/api/analytics/price-stats';

// --- Define and Export local types
export type FieldType =
  | "numeric"
  | "categorical"
  | "boolean"
  | "text"
  | "mixed"
  | "unknown";

export interface FieldValuePattern {
  type: FieldType;
  unit?: string;
  distinct_values?: number;
  value_examples?: string[];
  stats?: Record<string, any>;
}

export interface FieldDistribution {
  field_name: string;
  occurrence_count: number;
  distinct_value_count: number;
  top_values: [string, number][];
  field_type: FieldType;
  pattern: FieldValuePattern | null;
  cluster_id?: string;
}

export interface FieldMapping {
    original_field: string;
    target_field: string;
}

export interface FieldHarmonizationMapping {
  _id: string;
  name: string;
  description?: string;
  mappings: FieldMapping[];
  created_at: string;
  updated_at: string;
  is_active: boolean;
  created_by?: string;
  affected_listings: string[];
}

export interface SimilarityMatrix {
  fields: string[];
  scores: number[][];
  timestamp: string;
}

export interface SuggestMappingsPayload {
  similarity_threshold?: number;
  min_occurrence?: number;
  protected_fields?: string[];
}

export interface HarmonizationSuggestion {
    clusters: any[]; // Replace with actual FieldCluster type if needed
    suggested_mapping: Record<string, string>;
    impact: any; // Replace with actual FieldMappingImpact type if needed
    similarity_threshold: number;
    created_at: string;
}

export interface UmapFieldData {
  name: string;
  type: FieldType;
  count: number;
  coordinates: [number, number] | [number, number, number]; // Supports 2D or 3D
}

export interface FieldEmbeddingsUmapResponse {
  fields: UmapFieldData[];
  umap_params: {
    n_neighbors: number;
    min_dist: number;
    n_components: number;
    metric: string;
  };
}

// --- Define Request Payload Types ---

// Matches backend/schemas/field_harmonization.py::CreateMappingRequest
export interface CreateMappingPayload {
  name: string;
  description?: string;
  mappings: FieldMapping[];
  is_active?: boolean;
  created_by?: string;
}

// Matches backend/schemas/field_harmonization.py::UpdateMappingRequest
export interface UpdateMappingPayload {
  name?: string;
  description?: string;
  mappings_to_add?: FieldMapping[];
  mappings_to_remove?: string[]; // List of original_field names
  is_active?: boolean;
}

// Matches backend/routers/analytics/field_harmonization.py::calculate_mapping_impact payload
export interface CalculateImpactPayload {
  field_mapping: Record<string, string>;
}

// Matches backend/routers/analytics/field_harmonization.py::calculate_mapping_impact response
export interface FieldMappingImpactResponse {
    // Define based on backend schema backend/schemas/field_harmonization.py::FieldMappingImpact
    total_fields: number;
    total_mapped_fields: number;
    total_affected_documents: number;
    field_impacts: Record<string, Record<string, any>>;
    clusters: any[]; // Replace with FieldCluster if needed
    before_after_samples: Record<string, any>[];
}

// --- API Client Methods ---

const basePath = '/admin/field-harmonization'; // Update base path
const FIELD_HARMONIZATION_QUERY_KEY_PREFIX = 'fieldHarmonization';

// --- Query Hooks ---

export function useFieldDistribution(
    minOccurrence: number = 5,
    includeValues: boolean = true,
    topValuesLimit: number = 10
) {
  return useQuery<FieldDistribution[], Error>({
    queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'distribution', { minOccurrence, includeValues, topValuesLimit }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.append('min_occurrence', minOccurrence.toString());
      params.append('include_values', includeValues.toString());
      params.append('top_values_limit', topValuesLimit.toString());
      return apiClient._fetch(`${basePath}/distribution?${params}`);
    },
  });
}

export function useFieldMappings(days: number = 30) {
  return useQuery<FieldHarmonizationMapping[], Error>({
    queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'mappings', { days }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.append('days', days.toString());
      return apiClient._fetch(`${basePath}/mappings?${params}`);
    }
  });
}

export function useActiveFieldMapping() {
  return useQuery<FieldHarmonizationMapping[], Error>({ // Backend returns a list
    queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'mappings', 'active'],
    queryFn: async () => {
        try {
            return await apiClient._fetch(`${basePath}/mappings/active`);
        } catch (error: any) {
            // Allow other errors to propagate
            console.error("Error fetching active mapping:", error);
            throw error;
        }
    }
  });
}

export function useSimilarityMatrix(
    minOccurrence: number = 5,
    includeFieldValues: boolean = true // Renamed to match backend
) {
  return useQuery<SimilarityMatrix, Error>({
    queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'similarityMatrix', { minOccurrence, includeFieldValues }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.append('min_occurrence', minOccurrence.toString());
      params.append('include_field_values', includeFieldValues.toString());
      return apiClient._fetch(`${basePath}/similarity-matrix?${params}`);
    }
  });
}

export function useFieldEmbeddingsUmap(
  minOccurrence: number = 5,
  nNeighbors: number = 15,
  minDist: number = 0.1,
  nComponents: number = 2,
  metric: string = 'cosine'
) {
  return useQuery<FieldEmbeddingsUmapResponse, Error>({
    queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'embeddings', 'umap', { minOccurrence, nNeighbors, minDist, nComponents, metric }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.append('min_occurrence', minOccurrence.toString());
      params.append('n_neighbors', nNeighbors.toString());
      params.append('min_dist', minDist.toString());
      params.append('n_components', nComponents.toString());
      params.append('metric', metric);
      return apiClient._fetch(`${basePath}/embeddings/umap?${params}`);
    }
  });
}

// --- Mutation Hooks ---

export function useCreateFieldMappingMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<FieldHarmonizationMapping, Error, CreateMappingPayload>({
    mutationFn: (mapping) => apiClient._fetch(`${basePath}/mappings`, {
        method: 'POST',
        body: JSON.stringify(mapping),
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'mappings'] });
      // queryClient.invalidateQueries({ queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'mappings', 'active'] }); // Covered by broader invalidation
      toast({ title: "Success", description: `Mapping "${data.name}" created.` });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to create mapping." });
    },
  });
}

export function useUpdateFieldMappingMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<FieldHarmonizationMapping, Error, { mappingId: string; updates: UpdateMappingPayload }>({
    mutationFn: ({ mappingId, updates }) => apiClient._fetch(`${basePath}/mappings/${mappingId}`, {
        method: 'PATCH',
        body: JSON.stringify(updates),
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'mappings'] });
      toast({ title: "Success", description: `Mapping "${data.name}" updated.` });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to update mapping." });
    },
  });
}

export function useDeleteFieldMappingMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<void, Error, string>({
    mutationFn: (mappingId) => apiClient._fetch(`${basePath}/mappings/${mappingId}`, {
        method: 'DELETE',
    }), // No body needed for DELETE, returns 204
    onSuccess: (_, mappingId) => {
      queryClient.invalidateQueries({ queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'mappings'] });
      toast({ title: "Success", description: `Mapping deleted.` }); // Name might not be available here easily
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to delete mapping." });
    },
  });
}

export function useFieldMappingImpactMutation() {
  const { toast } = useToast();
  return useMutation<FieldMappingImpactResponse, Error, CalculateImpactPayload>({
    mutationFn: (payload) => apiClient._fetch(`${basePath}/mappings/impact`, {
        method: 'POST',
        body: JSON.stringify(payload.field_mapping), // Backend expects the dict directly
    }),
    onSuccess: () => {
      toast({ title: "Success", description: "Field mapping impact calculated." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to calculate impact." });
    },
  });
}

export function useSuggestFieldMappingsMutation() {
  const { toast } = useToast();
  return useMutation<HarmonizationSuggestion, Error, SuggestMappingsPayload | undefined>({ // Payload can be empty for defaults
    mutationFn: (payload = {}) => {
        const body = {
            similarity_threshold: payload.similarity_threshold ?? 0.75,
            min_occurrence: payload.min_occurrence ?? 5,
            protected_fields: payload.protected_fields ?? [],
        };
        return apiClient._fetch(`${basePath}/suggest-mappings`, {
            method: 'POST',
            body: JSON.stringify(body),
        });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Field mapping suggestions generated." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to suggest mappings." });
    },
  });
}

export function useInvalidateFieldEmbeddingsMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<{ message: string }, Error, void>({
    mutationFn: () => apiClient._fetch(`${basePath}/embeddings/invalidate`, {
        method: 'POST',
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'embeddings', 'umap'] });
      toast({ title: "Success", description: data.message || "Field embeddings invalidated." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to invalidate embeddings." });
    },
  });
}

export function useApplyMappingsRetroactivelyMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<{ message: string, processed_count: number, total_updated: number }, Error, number | undefined> ({
    mutationFn: (batchSize) => { // batchSize can be undefined for default
        const params = new URLSearchParams();
        if (batchSize !== undefined) {
            params.append('batch_size', batchSize.toString());
        }
        return apiClient._fetch(`${basePath}/mappings/apply-retroactive?${params.toString()}`, {
            method: 'POST',
            // No body needed for this trigger
        });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'mappings'] });
      queryClient.invalidateQueries({ queryKey: [FIELD_HARMONIZATION_QUERY_KEY_PREFIX, 'distribution'] });
      queryClient.invalidateQueries({ queryKey: [QUERY_API_QUERY_KEY_PREFIX, 'listings'] }); 
      queryClient.invalidateQueries({ queryKey: [PRICE_STATS_QUERY_KEY_PREFIX, 'priceStats'] }); 
      toast({ title: "Success", description: data.message || "Retroactive mapping application started." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Error", description: error.message || "Failed to apply mappings retroactively." });
    },
  });
}