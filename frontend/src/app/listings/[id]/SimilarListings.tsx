"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { Listing } from "@/lib/types";
import ListingCard from "@/components/ListingCard";

export default function SimilarListings({ listingId }: { listingId: string }) {
  const { data: listingsResponse, isLoading } = useQuery({
    queryKey: ["similar-listings", listingId],
    queryFn: () =>
      apiClient.getSimilarListings(
        listingId,
        ["type", "brand", "base_model", "model_variant"],
        0,
        12
      ),
  });

  if (!listingsResponse) {
    return <div>No similar listings found</div>;
  }

  if (isLoading) {
    return <div>Loading...</div>;
  }

  const listings = listingsResponse.map((response) => response.listing);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {listings.map((listing: Listing) => (
        <ListingCard key={listing._id} listing={listing} />
      ))}
    </div>
  );
}
