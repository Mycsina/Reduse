"use client";

import { Listing } from "@/lib/api/query/query";
import ListingCard from "@/app/listings/ListingCard";
import { useSimilarListings } from "@/lib/api/query/query";

export default function SimilarListings({ listingId }: { listingId: string }) {
  const { data: listingsResponse, isLoading } = useSimilarListings(
    listingId,
    0,
    12,
  );

  if (!listingsResponse) {
    return <div>No similar listings found</div>;
  }

  if (isLoading) {
    return <div>Loading...</div>;
  }

  const listings = listingsResponse.map(
    (response: { listing: Listing }) => response.listing,
  );

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {listings.map((listing: Listing) => (
        <ListingCard key={listing._id} listing={listing} />
      ))}
    </div>
  );
}
