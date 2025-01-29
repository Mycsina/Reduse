import { notFound } from "next/navigation";
import { Metadata } from "next";
import { apiClient } from "@/lib/api-client";
import ListingContent from "./ListingContent";
import { AnalysisStatus, Listing, AnalyzedListing } from "@/lib/types";
import UpdateStatsButton from "./UpdateStatsButton";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Listing Details",
  description: "View detailed information about a listing",
};

interface ListingResponse {
  listing: Listing;
  analysis: AnalyzedListing | null;
}

interface SimilarListingResponse {
  listing: Listing;
  analysis: AnalyzedListing | null;
}

export default async function ListingPage({
  params,
}: {
  params: { id: string };
}) {
  const resolvedParams = await params;
  const id = resolvedParams.id;

  try {
    // Fetch listing and its analysis
    const listingResponse = (await apiClient.getListing(id)) as ListingResponse;
    const listing = listingResponse.listing;
    const analysis = listingResponse.analysis;

    // Fetch initial similar listings
    const initialSimilarListingsResponse =
      listing.analysis_status === AnalysisStatus.COMPLETED
        ? ((await apiClient.getSimilarListings(
            id,
            ["type", "brand", "base_model", "model_variant"],
            0,
            10
          )) as SimilarListingResponse[])
        : [];

    const initialSimilarListings = initialSimilarListingsResponse.map(
      (response) => response.listing
    );
    const initialSimilarAnalyses = initialSimilarListingsResponse
      .map((response) => response.analysis)
      .filter(
        (analysis): analysis is NonNullable<typeof analysis> =>
          analysis !== null
      );

    // Fetch current model stats if we have a base model
    const modelStats = analysis?.base_model
      ? await apiClient.getCurrentModelStats(analysis.base_model)
      : null;

    // Convert model stats to the expected format
    const modelAnalytics =
      modelStats && analysis?.brand && analysis?.base_model
        ? [
            {
              brand: analysis.brand,
              base_model: analysis.base_model,
              count: modelStats.sample_size,
              avg_price: modelStats.avg_price,
              median_price: modelStats.median_price,
              min_price: modelStats.min_price,
              max_price: modelStats.max_price,
              timestamp: modelStats.timestamp,
            },
          ]
        : [];

    return (
      <>
        <UpdateStatsButton />
        <ListingContent
          listing={listing}
          analysis={analysis}
          initialSimilarListings={initialSimilarListings}
          initialSimilarAnalyses={initialSimilarAnalyses}
          modelAnalytics={modelAnalytics}
          listingId={id}
        />
      </>
    );
  } catch (error) {
    notFound();
  }
}
