import type { AnalysisStatus, AnalyzedListingDocument } from "@/lib/api/admin/analysis";
import { useQuery, useMutation } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

const queryBasePath = '/query'; // Define base path locally
const listingsPath = '/listings'; // Define sub-path locally
export const QUERY_API_QUERY_KEY_PREFIX = 'listingsApi'; // To avoid conflict with 'listings' from other contexts

/**
 * Type of filter group.
 */
export type FilterGroupType = "AND" | "OR";

/**
 * Operator for filter conditions.
 */
export type OperatorType =
  | "EQUALS"
  | "CONTAINS"
  | "REGEX"
  | "GT"
  | "LT"
  | "GTE"
  | "LTE"
  | "EQ_NUM";

export interface PriceFilter {
  min?: number | null;
  max?: number | null;
}

/**
 * Model for a single filter condition.
 */
export interface FilterCondition {
  field: string;
  operator: OperatorType; // Use OperatorType enum
  value: string;         // Changed from pattern
}

/**
 * Model for a group of filter conditions.
 */
export interface FilterGroup {
  type: FilterGroupType;
  conditions: (FilterCondition | FilterGroup)[];
}

export interface PriceRange {
  min?: number;
  max?: number;
}

export interface ListingQuery {
  price?: PriceRange;
  search_text?: string;
  filter?: FilterGroup;
  skip?: number;
  limit?: number;
}

export interface ListingDocument {
  _id?: string | null;
  original_id: string;
  site: string;
  title: string;
  url?: string;
  description?: string | null;
  price_str?: string;
  price_value: number | null;
  currency?: string | null;
  scraped_at?: string;
  last_checked_at?: string;
  photo_urls?: string[];
  analysis_status?: AnalysisStatus;
  created_at?: string;
  updated_at?: string;
  [key: string]: any;
}

export type Listing = ListingDocument;

// Type for the response when querying listings
export interface ListingResponse {
  listing: ListingDocument;
  analysis: AnalyzedListingDocument | null;
}

export interface InfoFieldsResponse {
  main_fields: string[];
  info_fields: string[];
}

// --- Query Hooks ---

// New exported fetch function
export async function fetchListings(query: ListingQuery = {}): Promise<ListingResponse[]> {
  return apiClient._fetch(`${queryBasePath}${listingsPath}`, {
    method: 'POST',
    body: JSON.stringify(query),
  });
}

export function useQueryListings(query: ListingQuery = {}) {
  return useQuery<ListingResponse[], Error>({
    queryKey: [QUERY_API_QUERY_KEY_PREFIX, 'search', query],
    queryFn: () => fetchListings(query), // Use the new fetch function
    // Consider keepPreviousData: true for pagination/filtering for better UX
  });
}

export function useAvailableFields() {
  return useQuery<InfoFieldsResponse, Error>({
    queryKey: [QUERY_API_QUERY_KEY_PREFIX, 'fields'],
    queryFn: () => apiClient._fetch(`${queryBasePath}${listingsPath}/fields`),
  });
}

export function useSimilarListings(listingId: string | null | undefined, skip: number = 0, limit: number = 12) {
  return useQuery<ListingResponse[], Error>({
    queryKey: [QUERY_API_QUERY_KEY_PREFIX, 'similar', listingId, { skip, limit }],
    queryFn: () => {
      if (!listingId) return Promise.reject(new Error("listingId is required"));
      return apiClient._fetch(
        `${queryBasePath}${listingsPath}/similar/${listingId}?skip=${skip}&limit=${limit}`,
        { method: "GET" }
      );
    },
    enabled: !!listingId,
  });
}

export function useListingById(listingId: string | null | undefined) {
  return useQuery<ListingResponse, Error>({
    queryKey: [QUERY_API_QUERY_KEY_PREFIX, 'detail', listingId],
    queryFn: () => {
      if (!listingId) return Promise.reject(new Error("listingId is required"));
      return apiClient._fetch(`/query/listings/by_id/${listingId}`);
    },
    enabled: !!listingId,
  });
}

// --- Mutation Hooks ---

export function useNaturalLanguageQueryMutation() {
  const { toast } = useToast();
  return useMutation<ListingQuery, Error, string>({
    mutationFn: (nlQuery: string) => 
        apiClient._fetch(`${queryBasePath}${listingsPath}/natural`, {
            method: 'POST',
            body: JSON.stringify({ query: nlQuery })
        }),
    onSuccess: (_) => {
      toast({ title: "Query Processed", description: "Natural language query processed successfully." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "NLQ Error", description: error.message || "Failed to process natural language query." });
    },
  });
}

// --- Server-callable data fetching functions ---
export async function fetchListingById(id: string): Promise<ListingResponse> {
  return apiClient._fetch(`/query/listings/by_id/${id}`);
}

export async function fetchSimilarListings(
  listingId: string, 
  skip: number = 0, 
  limit: number = 12
): Promise<ListingResponse[]> {
  return apiClient._fetch(
    `${queryBasePath}${listingsPath}/similar/${listingId}?skip=${skip}&limit=${limit}`,
    { method: "GET" }
  );
}