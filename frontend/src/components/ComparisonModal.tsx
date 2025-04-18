"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import Image from "next/image";
import { Listing, AnalyzedListing, ModelAnalytics } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { ChevronLeft, ChevronRight, ImageIcon } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api-client";
import { useRouter } from "next/navigation";
import PriceHistoryModal from "@/components/PriceHistoryModal";
import { toast } from "@/hooks/use-toast";

interface ComparisonData {
  field: string;
  current: string;
  similar: string;
  matches: boolean;
}

interface PriceStats {
  model: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  median_price: number;
  sample_size: number;
  timestamp: string;
}

interface ComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentListing: Listing;
  currentAnalysis: AnalyzedListing | null;
  similarListings: Listing[];
  similarAnalyses: AnalyzedListing[];
  modelAnalytics: ModelAnalytics[];
}

function getComparisonData(
  currentListing: Listing,
  currentAnalysis: AnalyzedListing | null,
  similarListing: Listing,
  similarAnalysis: AnalyzedListing
): ComparisonData[] {
  const data: ComparisonData[] = [
    {
      field: "Brand",
      current: currentAnalysis?.brand || "Unknown",
      similar: similarAnalysis.brand || "Unknown",
      matches:
        currentAnalysis?.brand === similarAnalysis.brand &&
        currentAnalysis?.brand !== null,
    },
    {
      field: "Model",
      current: currentAnalysis?.base_model || "Unknown",
      similar: similarAnalysis.base_model || "Unknown",
      matches:
        currentAnalysis?.base_model === similarAnalysis.base_model &&
        currentAnalysis?.base_model !== null,
    },
  ];

  // Add all info fields that exist in either listing
  const allInfoFields = new Set([
    ...Object.keys(currentAnalysis?.info || {}),
    ...Object.keys(similarAnalysis.info || {}),
  ]);

  allInfoFields.forEach((field) => {
    const currentValue = currentAnalysis?.info?.[field];
    const similarValue = similarAnalysis.info?.[field];
    data.push({
      field: field.replace(/_/g, " "),
      current: currentValue?.toString() || "-",
      similar: similarValue?.toString() || "-",
      matches:
        currentValue === similarValue &&
        currentValue !== undefined &&
        currentValue !== null,
    });
  });

  return data;
}

const PLACEHOLDER_IMAGE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='3' width='18' height='18' rx='2' ry='2'/%3E%3Ccircle cx='8.5' cy='8.5' r='1.5'/%3E%3Cpolyline points='21 15 16 10 5 21'/%3E%3C/svg%3E";

const getListingImage = (listing: Listing): string => {
  if (!listing.photo_urls || listing.photo_urls.length === 0) {
    return PLACEHOLDER_IMAGE;
  }
  return Array.isArray(listing.photo_urls)
    ? listing.photo_urls[0]
    : listing.photo_urls;
};

export default function ComparisonModal({
  isOpen,
  onClose,
  currentListing,
  currentAnalysis,
  similarListings: initialSimilarListings,
  similarAnalyses: initialSimilarAnalyses,
  modelAnalytics = [],
}: ComparisonModalProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [similarListings, setSimilarListings] = useState<Listing[]>(
    initialSimilarListings
  );
  const [similarAnalyses, setSimilarAnalyses] = useState<AnalyzedListing[]>(
    initialSimilarAnalyses
  );
  const [isLoading, setIsLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [nextBatch, setNextBatch] = useState<{
    listings: Listing[];
    analyses: AnalyzedListing[];
  } | null>(null);
  const [showPriceHistory, setShowPriceHistory] = useState<{
    brand: string;
    baseModel: string;
  } | null>(null);

  const router = useRouter();

  const maxIndex = similarListings.length - 1;
  const similarAnalysis = similarAnalyses[currentIndex] || null;

  // Prefetch next listing data
  const prefetchListingData = useCallback((listingId: string) => {
    // Use Next.js router prefetching
    router.prefetch(`/listings/${listingId}`);
    apiClient.getListing(listingId); // Prime SWR cache
    apiClient.getSimilarListings(
      listingId,
      ["type", "brand", "base_model", "model_variant"],
      0,
      5
    ); // Prefetch initial similars
  }, [router]);

  // Prefetch adjacent listings when current index changes
  useEffect(() => {
    if (isOpen && similarListings.length > 1) {
      const nextIndex = (currentIndex + 1) % similarListings.length;
      const prevIndex =
        currentIndex === 0 ? similarListings.length - 1 : currentIndex - 1;

      // Use Next.js Image component's built-in prefetching
      const prefetchImage = (url: string) => {
        const imgElement = document.createElement("link");
        imgElement.rel = "prefetch";
        imgElement.as = "image";
        imgElement.href = url;
        document.head.appendChild(imgElement);
      };

      // Add null checks before accessing properties
      if (similarListings[nextIndex]?.photo_urls?.[0]) {
        prefetchImage(similarListings[nextIndex].photo_urls[0]);
      }
      if (similarListings[prevIndex]?.photo_urls?.[0]) {
        prefetchImage(similarListings[prevIndex].photo_urls[0]);
      }

      if (similarListings[nextIndex]?._id) {
        prefetchListingData(similarListings[nextIndex]._id);
      }
      if (similarListings[prevIndex]?._id) {
        prefetchListingData(similarListings[prevIndex]._id);
      }
    }
  }, [isOpen, currentIndex, similarListings, router, prefetchListingData]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "d") {
        setCurrentIndex((prev) => {
          const next = prev + 1;
          return next < similarListings.length ? next : prev;
        });
      } else if (e.key === "ArrowLeft" || e.key === "a") {
        setCurrentIndex((prev) => (prev > 0 ? prev - 1 : prev));
      }
    },
    [similarListings.length]
  );

  useEffect(() => {
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  // Function to fetch the next batch of listings
  const fetchNextBatch = useCallback(async () => {
    try {
      setIsLoading(true);
      const newListingsResponse = await apiClient.getSimilarListings(
        currentListing._id!, // Add non-null assertion since we know this exists in this context
        ["type", "brand", "base_model", "model_variant"],
        similarListings.length,
        10
      );

      if (newListingsResponse.length > 0) {
        const newListings = newListingsResponse.map(
          (response: { listing: any }) => response.listing
        );
        const newAnalyses = newListingsResponse
          .map((response: { analysis: any }) => response.analysis)
          .filter(
            (analysis: any): analysis is AnalyzedListing => analysis !== null
          );

        if (newListings.length > 0) {
          setNextBatch({
            listings: newListings,
            analyses: newAnalyses,
          });
          setHasMore(true);
        } else {
          setHasMore(false);
        }
      } else {
        setHasMore(false);
      }
    } catch (error) {
      console.error("Error fetching next batch:", error);
      setHasMore(false);
    } finally {
      setIsLoading(false);
    }
  }, [currentListing._id, similarListings.length]);

  // Effect to prefetch next batch when we reach the middle of current batch
  useEffect(() => {
    if (!isOpen || !hasMore || isLoading || nextBatch) return;

    const prefetchThreshold = Math.floor(similarListings.length / 2);
    if (currentIndex >= prefetchThreshold) {
      fetchNextBatch();
    }
  }, [
    currentIndex,
    isOpen,
    hasMore,
    isLoading,
    nextBatch,
    similarListings.length,
    fetchNextBatch,
  ]);

  // Effect to append next batch when we're close to the end
  useEffect(() => {
    if (!isOpen || !nextBatch) return;

    const appendThreshold = similarListings.length - 3;
    if (currentIndex >= appendThreshold) {
      setSimilarListings((prev) => [...prev, ...nextBatch.listings]);
      setSimilarAnalyses((prev) => [...prev, ...nextBatch.analyses]);
      setNextBatch(null);
    }
  }, [currentIndex, isOpen, nextBatch, similarListings.length]);

  const similarListing = similarListings[currentIndex];

  const comparisonData = getComparisonData(
    currentListing,
    currentAnalysis,
    similarListing,
    similarAnalysis
  );

  const matchingFeatures = comparisonData.filter((item) => item.matches);
  const nonMatchingFeatures = comparisonData.filter((item) => !item.matches);

  const canGoNext = currentIndex < similarListings.length - 1;
  const canGoPrev = currentIndex > 0;

  const handleNext = () => {
    if (canGoNext) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrev = () => {
    if (canGoPrev) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const PriceInfo = ({
    listing,
    analysis,
  }: {
    listing: Listing;
    analysis: AnalyzedListing | null;
  }) => {
    const [stats, setStats] = useState<PriceStats | null>(null);
    const [isUpdating, setIsUpdating] = useState(false);

    useEffect(() => {
      if (analysis?.base_model) {
        apiClient
          .getCurrentModelStats(analysis.base_model)
          .then((data) => {
            setStats({ ...data, model: analysis.base_model });
          })
          .catch((error) => {
            console.error("Failed to fetch model stats:", error);
          });
      }
    }, [analysis?.base_model]);

    const handleUpdateStats = async () => {
      setIsUpdating(true);
      try {
        await apiClient.updatePriceStats();
        toast({
          title: "Updating price statistics",
          description: "This may take a few minutes",
        });
        // Refetch after a delay to allow for background processing
        setTimeout(() => {
          if (analysis?.base_model) {
            apiClient
              .getCurrentModelStats(analysis.base_model)
              .then((data) => setStats(data))
              .catch((error) =>
                console.error("Failed to fetch updated stats:", error)
              );
          }
        }, 5000); // Wait 5 seconds before refetching
      } catch (error) {
        toast({
          title: "Failed to update statistics",
          description:
            error instanceof Error ? error.message : "Unknown error occurred",
          variant: "destructive",
        });
      } finally {
        setIsUpdating(false);
      }
    };

    return (
      <div className="text-center">
        <p className="text-lg font-bold text-primary">
          {formatPrice(listing.price_value ? parseFloat(listing.price_value) : 0)}
        </p>
        {stats && stats.sample_size >= 3 ? (
          <div className="text-sm text-muted-foreground space-y-1">
            <Button
              variant="ghost"
              size="sm"
              className="text-sm p-0 h-auto hover:bg-transparent"
              onClick={() => {
                if (analysis?.brand && analysis?.base_model) {
                  setShowPriceHistory({
                    brand: analysis.brand,
                    baseModel: analysis.base_model,
                  });
                }
              }}
            >
              <p>Model median: {formatPrice(stats.median_price)}</p>
            </Button>
            <p className="text-xs">Based on {stats.sample_size} listings</p>
            <p className="text-xs text-muted-foreground">
              Last updated: {new Date(stats.timestamp).toLocaleString()}
            </p>
          </div>
        ) : stats?.sample_size ? (
          <p className="text-xs text-muted-foreground">
            Not enough data for reliable statistics
            <br />
            (only {stats.sample_size}{" "}
            {stats.sample_size === 1 ? "listing" : "listings"})
          </p>
        ) : (
          <div className="text-xs text-muted-foreground mt-1">
            <p>No price statistics available</p>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-6 mt-1"
              onClick={handleUpdateStats}
              disabled={isUpdating}
            >
              {isUpdating ? "Updating..." : "Update Stats"}
            </Button>
          </div>
        )}
      </div>
    );
  };

  const handleListingClick = (listingId: string) => {
    window.location.href = `/listings/${listingId}`;
    onClose();
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-w-[800px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Listing Comparison</DialogTitle>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-6">
            {/* Current Listing */}
            <div>
              <div>
                <div
                  className="relative aspect-video w-full mb-2 group cursor-pointer"
                  onClick={() => handleListingClick(currentListing._id)}
                >
                  <Image
                    src={getListingImage(currentListing)}
                    alt={currentListing.title}
                    fill
                    className={`object-cover rounded-lg transition-opacity group-hover:opacity-90 ${
                      !currentListing.photo_urls ||
                      currentListing.photo_urls.length === 0
                        ? "bg-muted p-4 object-contain"
                        : ""
                    }`}
                  />
                  {(!currentListing.photo_urls ||
                    currentListing.photo_urls.length === 0) && (
                    <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                      <ImageIcon className="w-12 h-12" />
                    </div>
                  )}
                </div>
                <div className="text-center">
                  <p className="font-semibold text-sm mb-1 h-10 line-clamp-2 group-hover:text-primary transition-colors">
                    {currentListing.title}
                  </p>
                  <PriceInfo listing={currentListing} analysis={currentAnalysis} />
                </div>
              </div>
            </div>

            {/* Similar Listing */}
            <div className="relative">
              <div
                className="group cursor-pointer"
                onClick={() => handleListingClick(similarListing._id)}
                onMouseEnter={() => prefetchListingData(similarListing._id)}
              >
                <div>
                  <div className="relative aspect-video w-full mb-2">
                    <Image
                      src={getListingImage(similarListing)}
                      alt={similarListing.title}
                      fill
                      className={`object-cover rounded-lg transition-opacity group-hover:opacity-90 ${
                        !similarListing.photo_urls ||
                        similarListing.photo_urls.length === 0
                          ? "bg-muted p-4 object-contain"
                          : ""
                      }`}
                    />
                    {(!similarListing.photo_urls ||
                      similarListing.photo_urls.length === 0) && (
                      <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                        <ImageIcon className="w-12 h-12" />
                      </div>
                    )}
                  </div>
                  <div className="text-center">
                    <p className="font-semibold text-sm mb-1 h-10 line-clamp-2 group-hover:text-primary transition-colors">
                      {similarListing.title}
                    </p>
                    <PriceInfo listing={similarListing} analysis={similarAnalysis} />
                  </div>
                </div>
              </div>

              {/* Navigation Buttons */}
              <div className="absolute inset-y-0 -left-4 -right-4 flex items-center justify-between pointer-events-none">
                <Button
                  variant="ghost"
                  size="icon"
                  className={`pointer-events-auto ${
                    canGoPrev
                      ? "opacity-100 hover:bg-background/80"
                      : "opacity-0 cursor-not-allowed"
                  }`}
                  onClick={handlePrev}
                  disabled={!canGoPrev}
                >
                  <ChevronLeft className="h-4 w-4" />
                  <span className="sr-only">Previous similar listing</span>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={`pointer-events-auto ${
                    canGoNext
                      ? "opacity-100 hover:bg-background/80"
                      : "opacity-0 cursor-not-allowed"
                  }`}
                  onClick={handleNext}
                  disabled={!canGoNext}
                >
                  <ChevronRight className="h-4 w-4" />
                  <span className="sr-only">Next similar listing</span>
                </Button>
              </div>
            </div>
          </div>

          {/* Matching Features */}
          {matchingFeatures.length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold mb-3">Matching Features</h3>
              <div className="space-y-2">
                {matchingFeatures.map((feature) => (
                  <div key={feature.field} className="text-center">
                    <p className="text-sm text-muted-foreground capitalize mb-1">
                      {feature.field}
                    </p>
                    <p className="font-medium">{feature.current}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Different Features */}
          {nonMatchingFeatures.length > 0 && (
            <div className="mt-6">
              <h3 className="text-lg font-semibold mb-3">Different Features</h3>
              <div className="space-y-4">
                {nonMatchingFeatures.map((feature) => (
                  <div key={feature.field} className="grid grid-cols-2 gap-6">
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground capitalize mb-1">
                        {feature.field}
                      </p>
                      <p className="font-medium">{feature.current}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground capitalize mb-1">
                        {feature.field}
                      </p>
                      <p className="font-medium">{feature.similar}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      {showPriceHistory && (
        <PriceHistoryModal
          isOpen={true}
          onClose={() => setShowPriceHistory(null)}
          brand={showPriceHistory.brand}
          baseModel={showPriceHistory.baseModel}
        />
      )}
    </>
  );
}
