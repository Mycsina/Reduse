import { notFound } from "next/navigation";
import { Metadata } from "next";
import { apiClient } from "@/lib/api-client";
import ListingContent from "./ListingContent";
import { AnalysisStatus } from "@/lib/types";
import UpdateStatsButton from "./UpdateStatsButton";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Listing Details",
  description: "View detailed information about a listing",
};

export default async function ListingPage({
  params,
}: {
  params: { id: string };
}) {
  const aw_params = await params;
  const id = aw_params.id;

  try {
    // Fetch listing and its analysis
    const listingResponse = await apiClient.getListing(id);
    const listing = listingResponse.listing;
    const analysis = listingResponse.analysis;

    // Fetch initial similar listings
    const initialSimilarListingsResponse =
      listing.analysis_status === AnalysisStatus.COMPLETED
        ? await apiClient.getSimilarListings(
            id,
            ["type", "brand", "base_model", "model_variant"],
            0,
            10
          )
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

    // Fetch model analytics for all relevant models
    const modelAnalytics = analysis?.base_model
      ? await apiClient.getModelAnalytics(analysis.base_model)
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
