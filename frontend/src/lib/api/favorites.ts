// API functions for managing favorite searches
import type { ListingQuery, ListingDocument } from '@/lib/api/query/query';
import type { AnalyzedListingDocument } from '@/lib/api/admin/analysis';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

const FAVORITES_BASE = '/favorites';
export const FAVORITES_QUERY_KEY_PREFIX = 'favorites';

// Types corresponding to backend schemas
export interface FavoriteSearchBase {
    name: string;
    query_params: Omit<ListingQuery, 'skip' | 'limit'>;
}

export interface FavoriteSearchCreate extends FavoriteSearchBase {}

export interface FavoriteSearchUpdate {
    name?: string;
}

export interface FavoriteSearchRead extends FavoriteSearchBase {
    _id: string; // PydanticObjectId serializes to string
    user_id: string;
    created_at: string; // datetime serializes to string
    last_viewed_at?: string;
    seen_listing_ids: string[];
    new_listings_count: number;
}

export interface FavoriteListingsResponse {
    favorite: FavoriteSearchRead;
    new_listings: [ListingDocument, AnalyzedListingDocument | null][];
    seen_listings: [ListingDocument, AnalyzedListingDocument | null][];
}

export interface MarkSeenRequest {
    listing_ids: string[];
}

// --- Query Hooks ---

export function useListFavoriteSearches() {
  return useQuery<FavoriteSearchRead[], Error>({
    queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'list'],
    queryFn: () => apiClient._fetch(FAVORITES_BASE, { method: 'GET' }),
  });
}

export function useFavoriteSearch(favoriteId: string | null | undefined) {
  return useQuery<FavoriteSearchRead, Error>({
    queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'detail', favoriteId],
    queryFn: () => {
      if (!favoriteId) return Promise.reject(new Error("Favorite ID is required"));
      return apiClient._fetch(`${FAVORITES_BASE}/${favoriteId}`, { method: 'GET' });
    },
    enabled: !!favoriteId,
  });
}

export function useFavoriteListingsSplit(favoriteId: string | null | undefined) {
  return useQuery<FavoriteListingsResponse, Error>({
    queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'listingsSplit', favoriteId],
    queryFn: () => {
      if (!favoriteId) return Promise.reject(new Error("Favorite ID is required"));
      return apiClient._fetch(`${FAVORITES_BASE}/${favoriteId}/listings`, { method: 'GET' });
    },
    enabled: !!favoriteId,
    staleTime: 0,
    gcTime: 0,
  });
}

// --- Mutation Hooks ---

export function useAddFavoriteSearchMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<FavoriteSearchRead, Error, FavoriteSearchCreate>({
    mutationFn: (favoriteData) => 
        apiClient._fetch(FAVORITES_BASE, {
            method: 'POST',
            body: JSON.stringify(favoriteData),
        }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'list'] });
      toast({ title: "Favorite Saved", description: `"${data.name}" has been added to your favorites.` });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Save Failed", description: error.message || "Could not save favorite search." });
    },
  });
}

export function useUpdateFavoriteSearchMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<FavoriteSearchRead, Error, { favoriteId: string; updateData: FavoriteSearchUpdate }>({
    mutationFn: ({ favoriteId, updateData }) => 
        apiClient._fetch(`${FAVORITES_BASE}/${favoriteId}`, {
            method: 'PATCH',
            body: JSON.stringify(updateData),
        }),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'list'] });
      queryClient.invalidateQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'detail', variables.favoriteId] });
      toast({ title: "Favorite Updated", description: `"${data.name}" has been updated.` });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Update Failed", description: error.message || "Could not update favorite search." });
    },
  });
}

export function useDeleteFavoriteSearchMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<void, Error, string>({
    mutationFn: (favoriteId) => 
        apiClient._fetch(`${FAVORITES_BASE}/${favoriteId}`, { method: 'DELETE' }),
    onSuccess: (_, favoriteId) => {
      queryClient.invalidateQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'list'] });
      queryClient.removeQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'detail', favoriteId] });
      queryClient.removeQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'listingsSplit', favoriteId] });
      toast({ title: "Favorite Removed", description: "The favorite search has been removed." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Remove Failed", description: error.message || "Could not remove favorite search." });
    },
  });
}

export function useMarkListingsAsSeenMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<void, Error, { favoriteId: string; listingIds: string[] }>({
    mutationFn: ({ favoriteId, listingIds }) => {
        const requestBody: MarkSeenRequest = { listing_ids: listingIds };
        return apiClient._fetch(`${FAVORITES_BASE}/${favoriteId}/mark_seen`, {
            method: 'PATCH',
            body: JSON.stringify(requestBody),
        });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'listingsSplit', variables.favoriteId] });
      // Also invalidate the detail if seen_listing_ids count/display changes on the favorite detail view
      queryClient.invalidateQueries({ queryKey: [FAVORITES_QUERY_KEY_PREFIX, 'detail', variables.favoriteId] });
      toast({ title: "Listings Marked Seen", description: "Selected listings have been marked as seen." });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Update Failed", description: error.message || "Could not mark listings as seen." });
    },
  });
} 