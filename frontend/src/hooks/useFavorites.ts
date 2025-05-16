import { useState, useEffect, useCallback } from 'react';
import { useQueryClient, useQuery, useMutation } from '@tanstack/react-query';
import apiClient from '../lib/api-client';
import type {
    FavoriteSearchRead,
    FavoriteSearchCreate,
    FavoriteSearchUpdate,
    FavoriteListingsResponse,
    MarkSeenRequest
} from '../lib/api/favorites';
import {
    useListFavoriteSearches,
    useAddFavoriteSearchMutation,
    useDeleteFavoriteSearchMutation,
    useUpdateFavoriteSearchMutation,
    useMarkListingsAsSeenMutation,
    useFavoriteListingsSplit,
    FAVORITES_QUERY_KEY_PREFIX
} from '@/lib/api/favorites';
import type { ListingQuery, ListingResponse, ListingDocument, PriceRange, FilterGroup, FilterGroupType, FilterCondition } from '../lib/api/query/query';
import type { AnalyzedListingDocument } from '../lib/api/admin/analysis';
import { isEqual } from 'lodash-es';
import { useToast } from '@/hooks/use-toast';

// Define the type for the normalized filter objects used in comparison
interface ComparableNormalizedQuery {
  price?: PriceRange; // min/max will be number | undefined
  search_text?: string;
  filter?: {
    type: FilterGroupType;
    conditions: (FilterCondition | FilterGroup)[];
  };
}

// Helper to sort filter conditions for robust comparison
const sortFilterConditions = (conditions: any[]) => {
  if (!conditions) return [];
  return [...conditions].sort((a, b) => {
    const fieldCompare = (a.field || "").localeCompare(b.field || "");
    if (fieldCompare !== 0) return fieldCompare;
    const operatorCompare = (a.operator || "").localeCompare(b.operator || "");
    if (operatorCompare !== 0) return operatorCompare;
    return String(a.value || "").localeCompare(String(b.value || ""));
  });
};

export function useFavoriteSearches(enabled: boolean = true) {
    const queryClient = useQueryClient();
    const { toast } = useToast();

    const { data: favorites = [], isLoading, error } = useListFavoriteSearches();

    const { mutateAsync: markListingsAsSeenAsync } = useMarkListingsAsSeenMutation();

    const addFavoriteBaseMutation = useAddFavoriteSearchMutation();
    const addFavorite = async (newFavoriteDataInput: FavoriteSearchCreate) => {
        try {
            const newlyCreatedFavorite = await addFavoriteBaseMutation.mutateAsync(newFavoriteDataInput);

            if (newlyCreatedFavorite._id && newFavoriteDataInput.query_params) {
                try {
                    const queryForListings: ListingQuery = {
                        ...newFavoriteDataInput.query_params,
                        skip: 0,
                        limit: 200,
                    };
                    const listingsResult: ListingResponse[] = await apiClient._fetch('/query/listings', {
                        method: 'POST',
                        body: JSON.stringify(queryForListings),
                    });
                    const listingIdsToMark = listingsResult.map(lr => lr.listing._id).filter(id => !!id) as string[];

                    if (listingIdsToMark.length > 0) {
                        await markListingsAsSeenAsync({ favoriteId: newlyCreatedFavorite._id, listingIds: listingIdsToMark });
                    }
                } catch (e: any) {
                    console.error("Failed to fetch or mark listings as seen for new favorite:", e);
                    toast({
                        title: "Favorite Saved (with a hiccup)",
                        description: `The favorite search itself was saved, but we could not automatically mark its current listings as 'seen': ${e.message || 'Unknown error'}. You can visit the favorite later to see all listings.`
                    });
                }
            }
            return newlyCreatedFavorite;
        } catch (addError: any) {
            console.error("Error in composed addFavorite:", addError);
            throw addError;
        }
    };

    const deleteFavoriteBaseMutation = useDeleteFavoriteSearchMutation();
    const removeFavorite = async (favoriteId: string) => {
        const currentFavorites = queryClient.getQueryData<FavoriteSearchRead[]>([FAVORITES_QUERY_KEY_PREFIX, 'list']) || [];
        const favoriteToRemove = currentFavorites.find(fav => fav._id === favoriteId);
        const removedName = favoriteToRemove?.name || 'Favorite';

        queryClient.setQueryData<FavoriteSearchRead[]>([FAVORITES_QUERY_KEY_PREFIX, 'list'], (oldData) =>
            oldData?.filter((fav) => fav._id !== favoriteId)
        );

        try {
            await deleteFavoriteBaseMutation.mutateAsync(favoriteId);
            toast({ title: "Success", description: `"${removedName}" removed from favorites.` });
        } catch (deleteError: any) {
            queryClient.setQueryData([FAVORITES_QUERY_KEY_PREFIX, 'list'], currentFavorites);
            console.error("Error in composed removeFavorite:", deleteError);
            throw deleteError;
        }
    };

    const updateFavoriteBaseMutation = useUpdateFavoriteSearchMutation();
    const updateFavorite = async (params: { id: string; data: FavoriteSearchUpdate }) => {
        const { id, data } = params;
        const queryKey = [FAVORITES_QUERY_KEY_PREFIX, 'list'];
        const previousFavorites = queryClient.getQueryData<FavoriteSearchRead[]>(queryKey);

        queryClient.setQueryData<FavoriteSearchRead[]>(queryKey, (oldData) =>
            oldData?.map((fav) =>
                fav._id === id ? { ...fav, ...data } : fav
            )
        );
        try {
            const updatedFavorite = await updateFavoriteBaseMutation.mutateAsync({ favoriteId: id, updateData: data });
            return updatedFavorite;
        } catch (updateError: any) {
            queryClient.setQueryData(queryKey, previousFavorites);
            console.error("Error in composed updateFavorite:", updateError);
            throw updateError;
        }
    };
    
    return {
        favorites: favorites || [],
        isLoading,
        error,
        addFavorite,
        removeFavorite,
        updateFavorite,
    };
}

export function useFavoriteStatus(currentFilters: ListingQuery | null, isAuthenticated: boolean) {
    const { favorites, isLoading: isLoadingFavoritesHook } = useFavoriteSearches(isAuthenticated); 
    const [isFavorite, setIsFavorite] = useState(false);
    const [favoriteId, setFavoriteId] = useState<string | null>(null);
    
    const isLoading = isLoadingFavoritesHook && (favorites === undefined || favorites.length === 0);

    useEffect(() => {
        if (!isAuthenticated || isLoading || !currentFilters || !favorites || favorites.length === 0) {
            setIsFavorite(false);
            setFavoriteId(null);
            return;
        }

        // --- Normalize currentFilters ---
        const comparableCurrentFilters: ComparableNormalizedQuery = {};
        if (currentFilters.price && (currentFilters.price.min !== undefined || currentFilters.price.max !== undefined)) {
            comparableCurrentFilters.price = {
                min: currentFilters.price.min ?? undefined,
                max: currentFilters.price.max ?? undefined,
            };
             // If both are undefined after ??, make price itself undefined
            if (comparableCurrentFilters.price.min === undefined && comparableCurrentFilters.price.max === undefined) {
                comparableCurrentFilters.price = undefined;
            }
        } else {
            comparableCurrentFilters.price = undefined;
        }

        if (currentFilters.search_text && currentFilters.search_text.trim() !== "") {
            comparableCurrentFilters.search_text = currentFilters.search_text.trim();
        } else {
            comparableCurrentFilters.search_text = undefined;
        }

        if (currentFilters.filter && currentFilters.filter.conditions && currentFilters.filter.conditions.length > 0) {
            comparableCurrentFilters.filter = {
                type: currentFilters.filter.type,
                conditions: sortFilterConditions(currentFilters.filter.conditions),
            };
        } else {
            comparableCurrentFilters.filter = undefined;
        }
        // Remove top-level undefined properties to match potential structure of fav.query_params
        Object.keys(comparableCurrentFilters).forEach(key => {
            const K = key as keyof ComparableNormalizedQuery;
            if (comparableCurrentFilters[K] === undefined) {
                delete comparableCurrentFilters[K];
            }
        });


        const matchedFavorite = favorites.find(fav => {
            // --- Normalize fav.query_params ---
            const comparableFavoriteFilters: ComparableNormalizedQuery = {};
            if (fav.query_params.price && (fav.query_params.price.min !== undefined || fav.query_params.price.max !== undefined)) {
                comparableFavoriteFilters.price = {
                    min: fav.query_params.price.min ?? undefined,
                    max: fav.query_params.price.max ?? undefined,
                };
                if (comparableFavoriteFilters.price.min === undefined && comparableFavoriteFilters.price.max === undefined) {
                    comparableFavoriteFilters.price = undefined;
                }
            } else {
                comparableFavoriteFilters.price = undefined;
            }

            if (fav.query_params.search_text && fav.query_params.search_text.trim() !== "") {
                comparableFavoriteFilters.search_text = fav.query_params.search_text.trim();
            } else {
                comparableFavoriteFilters.search_text = undefined;
            }

            if (fav.query_params.filter && fav.query_params.filter.conditions && fav.query_params.filter.conditions.length > 0) {
                comparableFavoriteFilters.filter = {
                    type: fav.query_params.filter.type,
                    conditions: sortFilterConditions(fav.query_params.filter.conditions),
                };
            } else {
                comparableFavoriteFilters.filter = undefined;
            }
            // Remove top-level undefined properties
            Object.keys(comparableFavoriteFilters).forEach(key => {
                const K = key as keyof ComparableNormalizedQuery;
                if (comparableFavoriteFilters[K] === undefined) {
                    delete comparableFavoriteFilters[K];
                }
            });
            
            return isEqual(comparableCurrentFilters, comparableFavoriteFilters);
        });
        if (matchedFavorite) {
            setIsFavorite(true);
            setFavoriteId(matchedFavorite._id);
        } else {
            setIsFavorite(false);
            setFavoriteId(null);
        }

    }, [currentFilters, favorites, isLoading, isAuthenticated]);

    return { isFavorite, favoriteId, isLoadingFavorites: isLoading };
}

export function useFavoriteListings(favoriteId: string | null) {
    const { 
        data: favoriteListingsData,
        isLoading, 
        error, 
        refetch 
    } = useFavoriteListingsSplit(favoriteId);

    const { mutateAsync: markListingsAsSeenAsync, ...markSeenMutationResult } = useMarkListingsAsSeenMutation(); 

    const markNewListingsAsSeen = useCallback(async () => {
        if (favoriteId && favoriteListingsData?.new_listings && favoriteListingsData.new_listings.length > 0) {
            const newListingIds = favoriteListingsData.new_listings.map(([listing, _analyzedListingDoc]: [ListingDocument, AnalyzedListingDocument | null]) => listing._id).filter((id: string | undefined | null) => !!id) as string[];
            if (newListingIds.length > 0) {
                try {
                    await markListingsAsSeenAsync({ favoriteId: favoriteId, listingIds: newListingIds });
                } catch (e) {
                    console.error("Failed to mark new listings as seen via composed hook:", e);
                }
            }
        }
    }, [favoriteId, favoriteListingsData?.new_listings, markListingsAsSeenAsync]);

    return {
        favoriteData: favoriteListingsData?.favorite,
        newListings: favoriteListingsData?.new_listings || [],
        seenListings: favoriteListingsData?.seen_listings || [],
        isLoading,
        error,
        refetchListings: refetch,
        markNewListingsAsSeen,
        isMarkingSeen: markSeenMutationResult.isPending, 
    };
} 