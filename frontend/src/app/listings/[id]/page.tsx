import { notFound } from "next/navigation";
import { Metadata } from "next";

import ListingContent from "./ListingContent";
import UpdateStatsButton from "./UpdateStatsButton";

import { fetchListingById, fetchSimilarListings } from "@/lib/api/query/query";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Listing Details",
  description: "View detailed information about a listing",
};

export default async function ListingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!id) {
    notFound();
  }

  // Fetch listing data
  const listingData = await fetchListingById(id); // Use server-callable function
  const listing = listingData.listing;
  const analysis = listingData.analysis;

  // Fetch initial similar listings
  const initialSimilarListingsData =
    listing.analysis_status === "completed"
      ? await fetchSimilarListings(id, 0, 12) // Use server-callable function
      : [];

  const initialSimilarListings = initialSimilarListingsData.map(
    (response) => response.listing,
  );
  const initialSimilarAnalyses = initialSimilarListingsData
    .map((response) => response.analysis)
    .filter(
      (analysis): analysis is NonNullable<typeof analysis> => analysis !== null,
    );

  return (
    <>
      <UpdateStatsButton />
      <ListingContent
        listing={listing}
        analysis={analysis}
        initialSimilarListings={initialSimilarListings}
        initialSimilarAnalyses={initialSimilarAnalyses}
        listingId={id}
      />
    </>
  );
}
