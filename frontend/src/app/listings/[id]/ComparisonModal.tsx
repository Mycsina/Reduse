"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import Image from "next/image";
import { AnalyzedListing } from "@/lib/api/admin/analysis";
import { Listing } from "@/lib/api/query/query";
import {
  useCurrentModelStats,
  useUpdatePriceStatsMutation,
} from "@/lib/api/analytics/price-stats";
import { formatPrice } from "@/lib/utils";
import {
  ChevronLeft,
  ChevronRight,
  ImageIcon,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import PriceHistoryModal from "@/app/listings/[id]/PriceHistoryModal";
import { toast } from "@/hooks/use-toast";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useQueryClient } from "@tanstack/react-query";
import { fetchListingById, fetchSimilarListings } from "@/lib/api/query/query";

interface ComparisonData {
  field: string;
  current: string;
  similar: string;
  status: "match" | "mismatch" | "missing_current" | "missing_similar";
}

interface ComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentListing: Listing;
  currentAnalysis: AnalyzedListing | null;
  similarListings: Listing[];
  similarAnalyses: AnalyzedListing[];
}

const safeStringLower = (val: any): string | null =>
  val != null ? String(val).toLowerCase() : null;

function getComparisonData(
  currentListing: Listing,
  currentAnalysis: AnalyzedListing | null,
  similarListing: Listing,
  similarAnalysis: AnalyzedListing | null,
): ComparisonData[] {
  const data: ComparisonData[] = [];

  const compareField = (
    fieldName: string,
    currentVal: any,
    similarVal: any,
  ) => {
    const currentExists = currentVal != null;
    const similarExists = similarVal != null;
    let status: ComparisonData["status"];

    if (currentExists && similarExists) {
      status =
        safeStringLower(currentVal) === safeStringLower(similarVal)
          ? "match"
          : "mismatch";
    } else if (currentExists && !similarExists) {
      status = "missing_similar";
    } else if (!currentExists && similarExists) {
      status = "missing_current";
    } else {
      // Should not happen if field exists in at least one, but handle defensively
      return; // Don't add if missing in both
    }

    data.push({
      field: fieldName.replace(/_/g, " "),
      current: currentExists ? String(currentVal) : "-",
      similar: similarExists ? String(similarVal) : "-",
      status: status,
    });
  };

  // Compare Brand
  compareField("Brand", currentAnalysis?.brand, similarAnalysis?.brand);

  // Compare Model
  compareField(
    "Model",
    currentAnalysis?.base_model,
    similarAnalysis?.base_model,
  );

  // Add all info fields that exist in either listing
  const allInfoFields = new Set([
    ...Object.keys(currentAnalysis?.info || {}),
    ...Object.keys(similarAnalysis?.info || {}),
  ]);

  allInfoFields.forEach((field) => {
    compareField(
      field,
      currentAnalysis?.info?.[field],
      similarAnalysis?.info?.[field],
    );
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
  similarListings: passedSimilarListings,
  similarAnalyses: passedSimilarAnalyses,
}: ComparisonModalProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showPriceHistory, setShowPriceHistory] = useState<{
    brand: string;
    baseModel: string;
  } | null>(null);

  const router = useRouter();
  const queryClient = useQueryClient();

  const maxIndex = passedSimilarListings.length - 1;
  const similarAnalysis = passedSimilarAnalyses[currentIndex] || null;

  // Prefetch next listing data
  const prefetchListingData = useCallback(
    (listingId: string) => {
      // Use Next.js router prefetching
      router.prefetch(`/listings/${listingId}`);
      // Prefetch with React Query
      queryClient.prefetchQuery({
        queryKey: ["listingsApi", "detail", listingId],
        queryFn: () => fetchListingById(listingId),
      });
      queryClient.prefetchQuery({
        queryKey: ["listingsApi", "similar", listingId, { skip: 0, limit: 5 }],
        queryFn: () => fetchSimilarListings(listingId, 0, 5),
      });
    },
    [router, queryClient],
  );

  // Prefetch adjacent listings when current index changes
  useEffect(() => {
    if (isOpen && passedSimilarListings.length > 1) {
      const nextIndex = (currentIndex + 1) % passedSimilarListings.length;
      const prevIndex =
        currentIndex === 0
          ? passedSimilarListings.length - 1
          : currentIndex - 1;

      // Use Next.js Image component's built-in prefetching
      const prefetchImage = (url: string) => {
        const imgElement = document.createElement("link");
        imgElement.rel = "prefetch";
        imgElement.as = "image";
        imgElement.href = url;
        document.head.appendChild(imgElement);
      };

      // Add null checks before accessing properties
      if (passedSimilarListings[nextIndex]?.photo_urls?.[0]) {
        prefetchImage(passedSimilarListings[nextIndex].photo_urls[0]);
      }
      if (passedSimilarListings[prevIndex]?.photo_urls?.[0]) {
        prefetchImage(passedSimilarListings[prevIndex].photo_urls[0]);
      }

      if (passedSimilarListings[nextIndex]?._id) {
        prefetchListingData(passedSimilarListings[nextIndex]._id);
      }
      if (passedSimilarListings[prevIndex]?._id) {
        prefetchListingData(passedSimilarListings[prevIndex]._id);
      }
    }
  }, [
    isOpen,
    currentIndex,
    passedSimilarListings,
    router,
    prefetchListingData,
  ]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "d") {
        setCurrentIndex((prev) => {
          const next = prev + 1;
          return next < passedSimilarListings.length ? next : prev;
        });
      } else if (e.key === "ArrowLeft" || e.key === "a") {
        setCurrentIndex((prev) => (prev > 0 ? prev - 1 : prev));
      }
    },
    [passedSimilarListings.length],
  );

  useEffect(() => {
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen || !passedSimilarListings || passedSimilarListings.length === 0) {
    return null;
  }

  const similarListing = passedSimilarListings[currentIndex];

  const comparisonContentData = getComparisonData(
    currentListing,
    currentAnalysis,
    similarListing,
    similarAnalysis,
  );

  const handleNext = () => {
    setCurrentIndex((prev) => {
      const next = prev + 1;
      return next < passedSimilarListings.length ? next : prev;
    });
  };

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : prev));
  };

  const PriceInfo = ({
    listingPrice,
    brand,
    baseModel,
  }: {
    listingPrice: number | null;
    brand: string | null | undefined;
    baseModel: string | null | undefined;
  }) => {
    const { data: statsData, isLoading: isLoadingStats } =
      useCurrentModelStats(baseModel);
    const { mutate: updateStats, isPending: isUpdatingStats } =
      useUpdatePriceStatsMutation();

    const handleUpdateStats = async () => {
      try {
        if (!baseModel) {
          toast({
            title: "Error",
            description: "Base model not available to update stats.",
            variant: "destructive",
          });
          return;
        }
        toast({
          title: "Updating price statistics",
          description: "This may take a few minutes.",
        });
        updateStats();
      } catch (error) {
        console.error("PriceInfo: Error during updateStats call", error);
      }
    };

    return (
      <div className="text-center">
        <p className="text-primary text-lg font-bold">
          {formatPrice(listingPrice ? Number(listingPrice) : 0)}
        </p>
        {isLoadingStats && (
          <p className="text-muted-foreground text-xs">Loading stats...</p>
        )}
        {!isLoadingStats &&
        statsData &&
        statsData.sample_size &&
        statsData.sample_size >= 3 ? (
          <div className="text-muted-foreground space-y-1 text-sm">
            <Button
              variant="ghost"
              size="sm"
              className="h-auto p-0 text-sm hover:bg-transparent"
              onClick={() => {
                if (brand && baseModel) {
                  setShowPriceHistory({
                    brand: brand,
                    baseModel: baseModel,
                  });
                }
              }}
              disabled={!statsData?.median_price}
            >
              <p>
                Model median:{" "}
                {statsData?.median_price
                  ? formatPrice(statsData.median_price)
                  : "N/A"}
              </p>
            </Button>
            <p className="text-xs">Based on {statsData.sample_size} listings</p>
            <p className="text-muted-foreground text-xs">
              Last updated:{" "}
              {statsData.timestamp
                ? new Date(statsData.timestamp).toLocaleString()
                : "N/A"}
            </p>
          </div>
        ) : !isLoadingStats && statsData?.sample_size ? (
          <p className="text-muted-foreground text-xs">
            Not enough data for reliable statistics
            <br />
            (only {statsData.sample_size}{" "}
            {statsData.sample_size === 1 ? "listing" : "listings"})
          </p>
        ) : !isLoadingStats ? (
          <div className="text-muted-foreground mt-1 text-xs">
            <p>No price statistics available for {baseModel || "this model"}</p>
            <Button
              variant="ghost"
              size="sm"
              className="mt-1 h-6 text-xs"
              onClick={handleUpdateStats}
              disabled={isUpdatingStats || !baseModel}
            >
              {isUpdatingStats ? "Updating..." : "Update Stats"}
            </Button>
          </div>
        ) : null}
      </div>
    );
  };

  const handleListingClick = (listingId: string | null | undefined) => {
    if (!listingId) return; // Prevent navigation if ID is missing
    window.location.href = `/listings/${listingId}`;
    onClose();
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-h-[90vh] max-w-[800px] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Listing Comparison</DialogTitle>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-6">
            {/* Current Listing */}
            <div>
              <div>
                <div
                  className="group relative mb-2 aspect-video w-full cursor-pointer"
                  onClick={() => handleListingClick(currentListing?._id)}
                >
                  <Image
                    src={getListingImage(currentListing)}
                    alt={currentListing.title}
                    fill
                    className={`rounded-lg object-cover transition-opacity group-hover:opacity-90 ${
                      !currentListing.photo_urls ||
                      currentListing.photo_urls.length === 0
                        ? "bg-muted object-contain p-4"
                        : ""
                    }`}
                  />
                  {(!currentListing.photo_urls ||
                    currentListing.photo_urls.length === 0) && (
                    <div className="text-muted-foreground absolute inset-0 flex items-center justify-center">
                      <ImageIcon className="h-12 w-12" />
                    </div>
                  )}
                </div>
                <div className="text-center">
                  <p className="group-hover:text-primary mb-1 line-clamp-2 h-10 text-sm font-semibold transition-colors">
                    {currentListing.title}
                  </p>
                  <PriceInfo
                    listingPrice={currentListing.price_value}
                    brand={currentAnalysis?.brand}
                    baseModel={currentAnalysis?.base_model}
                  />
                </div>
              </div>
            </div>

            {/* Similar Listing */}
            <div className="relative">
              <div
                className="group cursor-pointer"
                onClick={() => handleListingClick(similarListing?._id)}
                onMouseEnter={() => {
                  if (similarListing?._id) {
                    prefetchListingData(similarListing._id);
                  }
                }}
              >
                <div>
                  <div className="relative mb-2 aspect-video w-full">
                    <Image
                      src={getListingImage(similarListing)}
                      alt={similarListing.title}
                      fill
                      className={`rounded-lg object-cover transition-opacity group-hover:opacity-90 ${
                        !similarListing.photo_urls ||
                        similarListing.photo_urls.length === 0
                          ? "bg-muted object-contain p-4"
                          : ""
                      }`}
                    />
                    {(!similarListing.photo_urls ||
                      similarListing.photo_urls.length === 0) && (
                      <div className="text-muted-foreground absolute inset-0 flex items-center justify-center">
                        <ImageIcon className="h-12 w-12" />
                      </div>
                    )}
                  </div>
                  <div className="text-center">
                    <p className="group-hover:text-primary mb-1 line-clamp-2 h-10 text-sm font-semibold transition-colors">
                      {similarListing.title}
                    </p>
                    <PriceInfo
                      listingPrice={similarListing.price_value}
                      brand={similarAnalysis?.brand}
                      baseModel={similarAnalysis?.base_model}
                    />
                  </div>
                </div>
              </div>

              {/* Navigation Buttons */}
              <div className="pointer-events-none absolute inset-y-0 -right-4 -left-4 flex items-center justify-between">
                <Button
                  variant="ghost"
                  size="icon"
                  className={`pointer-events-auto ${
                    currentIndex > 0
                      ? "hover:bg-background/80 opacity-100"
                      : "cursor-not-allowed opacity-0"
                  }`}
                  onClick={handlePrev}
                  disabled={currentIndex === 0}
                >
                  <ChevronLeft className="h-4 w-4" />
                  <span className="sr-only">Previous similar listing</span>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={`pointer-events-auto ${
                    currentIndex < maxIndex
                      ? "hover:bg-background/80 opacity-100"
                      : "cursor-not-allowed opacity-0"
                  }`}
                  onClick={handleNext}
                  disabled={currentIndex === maxIndex}
                >
                  <ChevronRight className="h-4 w-4" />
                  <span className="sr-only">Next similar listing</span>
                </Button>
              </div>
            </div>
          </div>

          {/* Features Comparison */}
          {comparisonContentData.length > 0 && (
            <div className="mt-6">
              <h3 className="mb-4 text-lg font-semibold">Features</h3>
              <div className="space-y-3">
                {comparisonContentData.map((feature) => (
                  <div
                    key={feature.field}
                    className="grid grid-cols-[1fr_auto_1fr] items-center gap-4"
                  >
                    {/* Current Value */}
                    <div className="text-center">
                      <p className="font-medium">{feature.current}</p>
                    </div>
                    {/* Icon and Field Name */}
                    <div className="flex flex-col items-center text-center">
                      {feature.status === "match" ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : feature.status === "mismatch" ? (
                        <XCircle className="h-5 w-5 text-red-600" />
                      ) : feature.status === "missing_current" ? (
                        <TooltipProvider delayDuration={100}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <HelpCircle className="h-5 w-5 text-yellow-600" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Missing in current listing</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      ) : (
                        <TooltipProvider delayDuration={100}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <HelpCircle className="h-5 w-5 text-yellow-600" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Missing in similar listing</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                      <p className="text-muted-foreground mb-1 text-sm capitalize">
                        {feature.field}
                      </p>
                    </div>
                    {/* Similar Value */}
                    <div className="text-center">
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
