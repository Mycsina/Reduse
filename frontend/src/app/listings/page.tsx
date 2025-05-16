"use client";

import { Suspense, useEffect, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import ListingsGrid from "@/app/listings/ListingsGrid";
import ListingsFilter from "@/app/listings/ListingsFilter";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterGroup, ListingQuery, PriceRange } from "@/lib/api/query/query";
import { useFavoriteStatus, useFavoriteListings } from "@/hooks/useFavorites";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/providers/AuthProvider";
// Types
import type { ListingDocument, ListingResponse } from "@/lib/api/query/query";
import type { AnalyzedListingDocument } from "@/lib/api/admin/analysis";

// Define the structure for resolved filters
export interface ResolvedFilters {
  price_min?: number;
  price_max?: number;
  search_text?: string;
  advanced?: FilterGroup;
}

export default function ListingsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { isAuthenticated, isLoading: isLoadingAuth, user } = useAuth();

  // 1. Resolve filters from URL Search Params
  const resolvedFilters = useMemo((): ResolvedFilters => {
    let filters: ResolvedFilters = {};
    filters = {
      price_min: searchParams.get("price_min")
        ? Number(searchParams.get("price_min"))
        : undefined,
      price_max: searchParams.get("price_max")
        ? Number(searchParams.get("price_max"))
        : undefined,
      search_text: searchParams.get("search_text") || undefined,
      advanced: searchParams.get("advanced")
        ? (JSON.parse(searchParams.get("advanced")!) as FilterGroup)
        : undefined,
    };
    // Clean up empty advanced filter
    if (filters.advanced && filters.advanced.conditions.length === 0) {
      filters.advanced = undefined;
    }
    return filters;
  }, [searchParams]);

  // 2. Convert resolved filters to a comparable ListingQuery object
  const currentQuery = useMemo((): ListingQuery | null => {
    const price: PriceRange | undefined =
      resolvedFilters.price_min || resolvedFilters.price_max
        ? {
            min: resolvedFilters.price_min,
            max: resolvedFilters.price_max,
          }
        : undefined;

    if (!price && !resolvedFilters.search_text && !resolvedFilters.advanced) {
      return null; // No active filters
    }

    return {
      price: price,
      search_text: resolvedFilters.search_text,
      filter: resolvedFilters.advanced,
      skip: 0, // Normalize for comparison
      limit: 0, // Normalize for comparison
    };
  }, [resolvedFilters]);

  // 3. Check favorite status *only if authenticated*
  const {
    isFavorite,
    favoriteId,
    isLoadingFavorites, // Renamed from isLoading for clarity
  } = useFavoriteStatus(currentQuery, isAuthenticated);

  // 4. Fetch favorite listings *only if authenticated and current filters match a favorite*
  const shouldFetchFavoriteListings =
    isAuthenticated && isFavorite && !!favoriteId;
  const {
    favoriteData,
    newListings,
    seenListings,
    isLoading: isLoadingFavoriteListings, // Specific loading state for this fetch
    error: favoriteError,
    markNewListingsAsSeen,
    refetchListings: refetchFavoriteListings,
  } = useFavoriteListings(shouldFetchFavoriteListings ? favoriteId : null); // Enable only when needed

  // 5. Effect to mark listings as seen (only runs if authenticated & isFavorite)
  useEffect(() => {
    if (shouldFetchFavoriteListings && newListings.length > 0) {
      const timer = setTimeout(() => {
        markNewListingsAsSeen();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [shouldFetchFavoriteListings, newListings, markNewListingsAsSeen]);

  // 6. Effect to handle errors loading favorite data
  useEffect(() => {
    if (favoriteError) {
      toast({
        variant: "destructive",
        title: "Error Loading Favorite",
        description: `Could not load details for the favorite search: ${favoriteError.message}`,
      });
    }
  }, [favoriteError, toast]);

  // 7. Refetch favorite listings if the matching favoriteId changes
  useEffect(() => {
    if (shouldFetchFavoriteListings) {
      refetchFavoriteListings();
    }
  }, [shouldFetchFavoriteListings, refetchFavoriteListings]); // Refetch when shouldFetch becomes true

  // Combined loading state
  const isLoading =
    isLoadingAuth ||
    isLoadingFavorites ||
    (shouldFetchFavoriteListings && isLoadingFavoriteListings);

  // Format data for ListingsGrid
  const formatListingsForGrid = (
    data: [ListingDocument, AnalyzedListingDocument | null][],
  ): ListingResponse[] => {
    return data.map(([listing, analysis]) => ({ listing, analysis }));
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="mb-6 h-8 w-48" /> {/* Title skeleton */}
        <Skeleton className="mb-6 h-32 w-full" /> {/* Filter skeleton */}
        <Skeleton className="mt-6 h-[200px] w-full" /> {/* Grid skeleton */}
      </div>
    );
  }

  // Determine if we are *actually* in favorite view mode (authenticated and matches favorite)
  const isFavoriteView = isAuthenticated && isFavorite;

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="mb-6 text-3xl font-bold">
        {isFavoriteView && favoriteData
          ? `Watched: ${favoriteData.name}`
          : "Listings"}
      </h1>

      {/* ListingsFilter uses its own state + useFavoriteStatus based on currentQuery */}
      <ListingsFilter initialFilters={resolvedFilters} />

      {isFavoriteView ? (
        // --- Favorite View ---
        <div>
          {isLoadingFavoriteListings && !newListings && !seenListings ? (
            <Skeleton className="mt-6 h-[200px] w-full" />
          ) : (
            <>
              {newListings.length > 0 && (
                <>
                  <h2 className="mt-8 mb-4 text-2xl font-semibold">
                    New Listings ({newListings.length})
                  </h2>
                  <Suspense
                    fallback={<Skeleton className="h-[200px] w-full" />}
                  >
                    <ListingsGrid
                      listingsData={formatListingsForGrid(newListings)}
                      favoriteId={favoriteId || undefined}
                    />
                  </Suspense>
                </>
              )}
              {seenListings.length > 0 && (
                <>
                  <h2 className="mt-8 mb-4 text-2xl font-semibold">
                    Previously Seen Listings ({seenListings.length})
                  </h2>
                  <Suspense
                    fallback={<Skeleton className="h-[200px] w-full" />}
                  >
                    <ListingsGrid
                      listingsData={formatListingsForGrid(seenListings)}
                      favoriteId={favoriteId || undefined}
                    />
                  </Suspense>
                </>
              )}
              {newListings.length === 0 && seenListings.length === 0 && (
                <p className="mt-8 text-center text-gray-500">
                  No listings found matching this saved search.
                </p>
              )}
            </>
          )}
        </div>
      ) : (
        // --- Standard View ---
        <Suspense fallback={<Skeleton className="mt-6 h-[200px] w-full" />}>
          <ListingsGrid filters={resolvedFilters} />
        </Suspense>
      )}
    </div>
  );
}
