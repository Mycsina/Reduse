"use client";

import { apiClient } from "@/lib/api-client";
import { AnalysisStatus, FilterGroup, ListingResponse } from "@/lib/types";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { useInView } from "react-intersection-observer";
import { useVirtualizer, VirtualItem } from "@tanstack/react-virtual";
import ListingCard from "./ListingCard";

const ITEMS_PER_PAGE = 24;
const ESTIMATED_ITEM_HEIGHT = 300;
const ROW_PADDING = 32; // 16px top + 16px bottom (py-4 = 1rem = 16px)
const GRID_COLS = 4; // Fixed to 4 columns

interface ListingsGridProps {
  filters?: {
    price_min?: number;
    price_max?: number;
    status?: AnalysisStatus;
    site?: string;
    search_text?: string;
    advanced?: FilterGroup;
  };
}

export default function ListingsGrid({ filters = {} }: ListingsGridProps) {
  const { ref, inView } = useInView();
  const parentRef = useRef<HTMLDivElement>(null);

  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    status,
  } = useInfiniteQuery({
    queryKey: ["listings", filters],
    queryFn: async ({ pageParam = 0 }) => {
      const skip = pageParam * ITEMS_PER_PAGE;
      return apiClient.queryListings({
        price:
          filters.price_min || filters.price_max
            ? {
                min: filters.price_min,
                max: filters.price_max,
              }
            : undefined,
        status: filters.status,
        site: filters.site,
        search_text: filters.search_text,
        filter: filters.advanced,
        skip,
        limit: ITEMS_PER_PAGE,
        include_fields: ["type", "brand", "base_model", "model_variant"],
      });
    },
    getNextPageParam: (lastPage, pages) => {
      if (!lastPage || lastPage.length < ITEMS_PER_PAGE) return undefined;
      return pages.length;
    },
    initialPageParam: 0,
  });

  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Flatten the data to a single array, using memo to avoid re-rendering
  const allListings = useMemo(
    () => data?.pages.flatMap((page) => page) ?? [],
    [data?.pages]
  );

  // Virtualize the listings
  const rowVirtualizer = useVirtualizer({
    count: Math.ceil(allListings.length / GRID_COLS),
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_ITEM_HEIGHT + ROW_PADDING,
    overscan: 5,
  });

  if (status === "pending") return <div>Loading...</div>;
  if (status === "error") return <div>Error: {error.message}</div>;

  return (
    <div ref={parentRef} className="h-[800px] overflow-auto px-6">
      <div
        className="relative w-full"
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const rowStartIndex = virtualRow.index * GRID_COLS;
          const rowListings = allListings.slice(
            rowStartIndex,
            rowStartIndex + GRID_COLS
          );

          return (
            <div
              key={`row-${virtualRow.key}`}
              className="absolute left-0 right-0 grid grid-cols-4 gap-8 py-4"
              style={{
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              {rowListings.map((listingResponse, colIndex) => (
                <ListingCard
                  key={`${listingResponse.listing._id}-${
                    rowStartIndex + colIndex
                  }`}
                  listing={listingResponse.listing}
                  data-listing-visible={true}
                />
              ))}
            </div>
          );
        })}
      </div>
      <div ref={ref} className="h-1" id="load-more-trigger" />
    </div>
  );
}
