"use client";

import {
  FilterGroup,
  ListingQuery,
  FilterGroupType,
  fetchListings,
} from "@/lib/api/query/query";
import { AnalysisStatus } from "@/lib/api/admin/analysis";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useCallback } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import ListingCard from "./ListingCard";
import { ResolvedFilters } from "@/app/listings/page";
import throttle from "lodash.throttle";
import type { ListingResponse } from "@/lib/api/query/query"; // Import full response type
import type { InfiniteData, QueryKey } from "@tanstack/react-query"; // Added QueryKey

const ITEMS_PER_PAGE = 24;
const ESTIMATED_ITEM_HEIGHT = 300;
const ROW_PADDING = 32; // 16px top + 16px bottom (py-4 = 1rem = 16px)
const GRID_COLS = 4; // Fixed to 4 columns

interface ListingsGridProps {
  // Option 1: Pass filters for query
  filters?: ResolvedFilters & {
    status?: AnalysisStatus;
    site?: string;
  };
  // Option 2: Pass pre-fetched data (e.g., for favorites)
  listingsData?: ListingResponse[];
  favoriteId?: string; // Added favoriteId
}

export default function ListingsGrid({
  filters = {},
  listingsData,
  favoriteId, // Added favoriteId
}: ListingsGridProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  // Only fetch data if listingsData is not provided
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
    isLoading,
  } = useInfiniteQuery<
    ListingResponse[],
    Error,
    InfiniteData<ListingResponse[], number>,
    QueryKey,
    number
  >({
    queryKey: ["listings", filters],
    queryFn: async ({ pageParam = 0 }) => {
      const skip = pageParam * ITEMS_PER_PAGE;

      // Build the filter group dynamically (only if using filters)
      const baseFilter: FilterGroup = filters.advanced || {
        type: "AND" as FilterGroupType,
        conditions: [],
      };
      const conditions = [...baseFilter.conditions];

      if (filters.status) {
        conditions.push({
          field: "analysis_status",
          operator: "EQUALS",
          value: filters.status,
        });
      }
      if (filters.site) {
        conditions.push({
          field: "site",
          operator: "EQUALS",
          value: filters.site,
        });
      }
      const finalFilter: FilterGroup | undefined =
        conditions.length > 0 ? { ...baseFilter, conditions } : undefined;

      // Construct the ListingQuery body for the POST request
      const queryParams: ListingQuery = {
        price:
          filters.price_min || filters.price_max
            ? { min: filters.price_min, max: filters.price_max }
            : undefined,
        search_text: filters.search_text,
        filter: finalFilter,
        skip,
        limit: ITEMS_PER_PAGE,
      };

      return fetchListings(queryParams);
    },
    getNextPageParam: (lastPage, allPages) => {
      // Pagination only relevant when fetching data
      if (!listingsData && lastPage && lastPage.length >= ITEMS_PER_PAGE) {
        return allPages.length;
      }
      return undefined;
    },
    initialPageParam: 0,
    enabled: !listingsData, // Only enable the query if listingsData is NOT provided
  });

  // Determine the source of listings: pre-fetched or queried
  const allListings = useMemo(() => {
    if (listingsData) {
      // If data is passed directly, use it
      return listingsData;
    } else {
      // Otherwise, use the flattened data from the infinite query
      return data?.pages.flatMap((page: ListingResponse[]) => page) ?? [];
    }
  }, [listingsData, data?.pages]);

  // Virtualize the listings
  const rowVirtualizer = useVirtualizer({
    count: Math.ceil(allListings.length / GRID_COLS),
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_ITEM_HEIGHT + ROW_PADDING,
    overscan: 5,
  });

  // Scroll handling for infinite loading (only when NOT using listingsData)
  const handleScroll = useCallback(
    throttle(() => {
      // Don't fetch if data is pre-loaded or no more pages
      if (listingsData || !hasNextPage || isFetchingNextPage) return;

      const container = parentRef.current;
      if (!container) return;

      const { scrollTop, scrollHeight, clientHeight } = container;
      const totalVirtualHeight = rowVirtualizer.getTotalSize();
      const triggerPoint = totalVirtualHeight - clientHeight * 1.5; // Fetch when nearing the end

      if (scrollTop >= triggerPoint) {
        console.log("Fetching next page...");
        fetchNextPage();
      }
    }, 200),
    [
      listingsData,
      hasNextPage,
      isFetchingNextPage,
      fetchNextPage,
      rowVirtualizer,
    ],
  );

  useEffect(() => {
    const container = parentRef.current;
    // Only attach scroll listener if we are fetching data (not using listingsData)
    if (container && !listingsData) {
      container.addEventListener("scroll", handleScroll);
      return () => container.removeEventListener("scroll", handleScroll);
    }
  }, [handleScroll, listingsData]);

  // Handle loading/error states only when fetching data
  if (!listingsData) {
    if (isLoading) return <div>Loading listings...</div>;
    if (status === "error")
      return <div>Error loading listings: {error.message}</div>;
  }

  if (allListings.length === 0) {
    return <div className="py-10 text-center">No listings found.</div>;
  }

  return (
    <div ref={parentRef} className="h-[800px] overflow-auto px-6">
      <div
        className="relative w-full"
        style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const rowStartIndex = virtualRow.index * GRID_COLS;
          const rowListings = allListings.slice(
            rowStartIndex,
            rowStartIndex + GRID_COLS,
          );

          return (
            <div
              key={`row-${virtualRow.key}`}
              className="absolute right-0 left-0 grid grid-cols-1 gap-8 py-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
              style={{ transform: `translateY(${virtualRow.start}px)` }}
            >
              {rowListings.map(
                (listingResponse: ListingResponse, colIndex: number) => (
                  <ListingCard
                    key={`${listingResponse.listing.id || rowStartIndex + colIndex}`}
                    listing={listingResponse.listing}
                    analysis={listingResponse.analysis}
                    favoriteId={favoriteId} // Pass favoriteId to ListingCard
                  />
                ),
              )}
            </div>
          );
        })}
      </div>
      {!listingsData && isFetchingNextPage && (
        <div className="py-4 text-center">Loading more...</div>
      )}
    </div>
  );
}
