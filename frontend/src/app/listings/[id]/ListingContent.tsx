"use client";

import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import Image from "next/image";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatPrice } from "@/lib/utils";
import {
  Listing,
  AnalysisStatus,
  AnalyzedListing,
  ModelAnalytics,
} from "@/lib/types";
import { ChevronLeft, ChevronRight, X, Flag } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "@/components/ui/visually-hidden";
import { apiClient } from "@/lib/api-client";

// Lazy load heavy components
const ComparisonModal = lazy(() => import("@/components/ComparisonModal"));
const BugReportModal = lazy(() => import("@/components/BugReportModal"));

interface ListingContentProps {
  listing: Listing;
  analysis: AnalyzedListing | null;
  initialSimilarListings: Listing[];
  initialSimilarAnalyses: AnalyzedListing[];
  modelAnalytics: ModelAnalytics[];
  listingId: string;
}

export default function ListingContent({
  listing,
  analysis,
  initialSimilarListings,
  initialSimilarAnalyses,
  modelAnalytics,
  listingId,
}: ListingContentProps) {
  const [similarListings, setSimilarListings] = useState<Listing[]>(
    initialSimilarListings
  );
  const [similarAnalyses, setSimilarAnalyses] = useState<AnalyzedListing[]>(
    initialSimilarAnalyses
  );
  const [isLoading, setIsLoading] = useState(false);
  const [hasMore, setHasMore] = useState(initialSimilarListings.length === 10);
  const [nextBatch, setNextBatch] = useState<{
    listings: Listing[];
    analyses: AnalyzedListing[];
  } | null>(null);
  const [isComparisonModalOpen, setIsComparisonModalOpen] = useState(false);
  const [isBugReportModalOpen, setIsBugReportModalOpen] = useState(false);
  const [currentImageGroup, setCurrentImageGroup] = useState(0);
  const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(
    null
  );

  // Ensure photos_url is always an array
  const photos = Array.isArray(listing.photo_urls)
    ? listing.photo_urls
    : [listing.photo_urls];

  // Calculate number of groups
  const groupSize = 4;
  const numGroups = Math.ceil(photos.length / groupSize);

  // Get current group of photos
  const currentPhotos = photos.slice(
    currentImageGroup * groupSize,
    (currentImageGroup + 1) * groupSize
  );

  // Memoize handlers
  const handlePrevGroup = useCallback(() => {
    setCurrentImageGroup((prev) => (prev === 0 ? numGroups - 1 : prev - 1));
  }, [numGroups]);

  const handleNextGroup = useCallback(() => {
    setCurrentImageGroup((prev) => (prev + 1) % numGroups);
  }, [numGroups]);

  const handlePrevImage = useCallback(() => {
    if (selectedImageIndex === null) return;
    setSelectedImageIndex(
      selectedImageIndex === 0 ? photos.length - 1 : selectedImageIndex - 1
    );
  }, [selectedImageIndex, photos.length]);

  const handleNextImage = useCallback(() => {
    if (selectedImageIndex === null) return;
    setSelectedImageIndex((selectedImageIndex + 1) % photos.length);
  }, [selectedImageIndex, photos.length]);

  const handleImageClick = (groupIndex: number, imageIndex: number) => {
    const actualIndex = currentImageGroup * groupSize + imageIndex;
    setSelectedImageIndex(actualIndex);
  };

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't handle keyboard navigation if comparison modal is open
    if (isComparisonModalOpen) return;

    // Handle detail view navigation
    if (selectedImageIndex !== null) {
      if (e.key === "ArrowLeft" || e.key === "a") {
        e.preventDefault();
        handlePrevImage();
      } else if (e.key === "ArrowRight" || e.key === "d") {
        e.preventDefault();
        handleNextImage();
      } else if (e.key === "Escape") {
        setSelectedImageIndex(null);
      }
    }
    // Handle grid view navigation
    else if (numGroups > 1) {
      if (e.key === "ArrowLeft" || e.key === "a") {
        e.preventDefault();
        handlePrevGroup();
      } else if (e.key === "ArrowRight" || e.key === "d") {
        e.preventDefault();
        handleNextGroup();
      }
    }
  }, [isComparisonModalOpen, selectedImageIndex, handlePrevImage, handleNextImage, numGroups, handlePrevGroup, handleNextGroup]);

  // Add keyboard event listener
  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Function to fetch the next batch of listings
  const fetchNextBatch = useCallback(async () => {
    try {
      const skip = similarListings.length;
      const newListingsResponse = await apiClient.getSimilarListings(
        listingId,
        ["type", "brand", "base_model", "model_variant"],
        skip,
        10
      );

      if (newListingsResponse.length > 0) {
        const newListings = newListingsResponse.map(
          (response: { listing: any; }) => response.listing
        );
        const newAnalyses = newListingsResponse
          .map((response: { analysis: any; }) => response.analysis)
          .filter((analysis: any): analysis is AnalyzedListing => analysis !== null);

        // Filter out any listings we already have
        const existingIds = new Set(similarListings.map((l) => l._id));
        const filteredNewListings = newListings.filter(
          (l: { _id: string; }) => !existingIds.has(l._id)
        );
        const filteredNewAnalyses = newAnalyses.filter(
          (_: any, i: string | number) => !existingIds.has(newListings[i]._id)
        );

        return {
          listings: filteredNewListings,
          analyses: filteredNewAnalyses,
        };
      }
      return null;
    } catch (error) {
      console.error("Error fetching next batch:", error);
      return null;
    }
  }, [similarListings, listingId]);

  // Effect to prefetch next batch when we reach the middle of current batch
  useEffect(() => {
    const prefetchThreshold = Math.floor(similarListings.length / 2);
    const visibleListings = document.querySelectorAll(
      '[data-listing-visible="true"]'
    );
    const lastVisibleIndex = Array.from(visibleListings).length - 1;

    if (
      lastVisibleIndex >= prefetchThreshold &&
      !nextBatch &&
      !isLoading &&
      hasMore
    ) {
      setIsLoading(true);
      fetchNextBatch().then((batch) => {
        setNextBatch(batch);
        setHasMore(batch !== null && batch.listings.length > 0);
        setIsLoading(false);
      });
    }
  }, [similarListings, isLoading, hasMore, nextBatch, fetchNextBatch]);

  // Function to append the next batch when needed
  const appendNextBatch = useCallback(() => {
    if (nextBatch) {
      setSimilarListings((prev) => [...prev, ...nextBatch.listings]);
      setSimilarAnalyses((prev) => [...prev, ...nextBatch.analyses]);
      setNextBatch(null);
    }
  }, [nextBatch]);

  // Effect to handle intersection observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && nextBatch) {
          appendNextBatch();
        }
      },
      { threshold: 0.5 }
    );

    const loadMoreTrigger = document.getElementById("load-more-trigger");
    if (loadMoreTrigger) {
      observer.observe(loadMoreTrigger);
    }

    return () => {
      if (loadMoreTrigger) {
        observer.unobserve(loadMoreTrigger);
      }
    };
  }, [appendNextBatch, nextBatch]);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          {/* Main content */}
          <Card className="overflow-hidden">
            {/* Photos section */}
            <div className="relative bg-muted">
              <div className="relative">
                <div className="grid grid-cols-2 gap-2 aspect-[4/3]">
                  {currentPhotos.map((url, index) => (
                    <div
                      key={index}
                      className={`relative ${
                        currentPhotos.length === 1
                          ? "col-span-2 row-span-2"
                          : currentPhotos.length === 2
                          ? "col-span-1 row-span-2"
                          : currentPhotos.length === 3 && index === 0
                          ? "col-span-2"
                          : ""
                      } cursor-pointer group`}
                      onClick={() => handleImageClick(currentImageGroup, index)}
                    >
                      <Image
                        src={url ?? ''}
                        alt={`${listing.title} - Photo ${index + 1}`}
                        fill
                        className="object-cover rounded-lg transition-opacity group-hover:opacity-90"
                      />
                    </div>
                  ))}
                </div>

                {/* Navigation Buttons */}
                {numGroups > 1 && (
                  <>
                    <Button
                      variant="outline"
                      size="icon"
                      className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white group"
                      onClick={handlePrevGroup}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      <span className="sr-only">Previous group</span>
                      <span className="absolute left-full ml-2 px-2 py-1 bg-black/75 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                        Press A or ←
                      </span>
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white group"
                      onClick={handleNextGroup}
                    >
                      <ChevronRight className="h-4 w-4" />
                      <span className="sr-only">Next group</span>
                      <span className="absolute right-full mr-2 px-2 py-1 bg-black/75 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                        Press D or →
                      </span>
                    </Button>
                    {/* Group Indicator */}
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/50 text-white px-2 py-1 rounded-full text-sm">
                      {currentImageGroup + 1} / {numGroups}
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Listing details */}
            <div className="p-6">
              <div className="flex justify-between items-start">
                <h1 className="text-2xl font-bold mb-4">{listing.title}</h1>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setIsBugReportModalOpen(true)}
                  className="flex items-center gap-1 text-muted-foreground"
                >
                  <Flag className="h-4 w-4" />
                  <span>Report</span>
                </Button>
              </div>
              
              <div>
                <p className="text-3xl font-bold text-primary">
                  {formatPrice(listing.price_value ? parseFloat(listing.price_value) : 0)}
                </p>
              </div>

              <div>
                <h2 className="text-lg font-semibold mb-2">Description</h2>
                <p className="whitespace-pre-wrap">{listing.description}</p>
              </div>
            </div>
          </Card>

          {/* Analysis Information */}
          <div>
            <Card className="p-6 mb-6">
              <h2 className="text-xl font-semibold mb-4">Analysis Details</h2>
              {listing.analysis_status === AnalysisStatus.COMPLETED && analysis ? (
                <div className="space-y-4">
                  <div>
                    <label className="text-sm text-muted-foreground">Type</label>
                    <p className="font-medium">{analysis.type || "Unknown"}</p>
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">Brand</label>
                    <p className="font-medium">{analysis.brand || "Unknown"}</p>
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">
                      Base Model
                    </label>
                    <p className="font-medium">
                      {analysis.base_model || "Unknown"}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">
                      Model Variant
                    </label>
                    <p className="font-medium">
                      {analysis.model_variant || "Unknown"}
                    </p>
                  </div>
                  {/* Additional analyzed info */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.entries(analysis.info || {}).map(([key, value]) => (
                      <div key={key} className="flex items-start space-x-2">
                        <span className="text-muted-foreground">•</span>
                        <div>
                          <span className="text-sm text-muted-foreground capitalize">
                            {key.replace(/_/g, " ")}:
                          </span>
                          <span className="ml-1 font-medium">{String(value)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground">
                  {listing.analysis_status === AnalysisStatus.PENDING && (
                    <p>This listing is pending analysis.</p>
                  )}
                  {listing.analysis_status === AnalysisStatus.IN_PROGRESS && (
                    <p>Analysis is currently in progress.</p>
                  )}
                  {listing.analysis_status === AnalysisStatus.FAILED && (
                    <p>Analysis failed for this listing.</p>
                  )}
                </div>
              )}
            </Card>

            {/* Comparison Buttons */}
            {listing.analysis_status === AnalysisStatus.COMPLETED &&
              similarListings.length > 0 &&
              similarAnalyses.length > 0 && (
                <div className="space-y-2">
                  <Button
                    className="w-full"
                    onClick={() => setIsComparisonModalOpen(true)}
                  >
                    Quick Compare
                  </Button>
                  <Link href={`/comparison/${listing._id}`}>
                    <Button className="w-full" variant="outline">
                      Detailed Comparison
                    </Button>
                  </Link>
                </div>
              )}
          </div>
        </div>

        {/* Image Detail Modal */}
        <Dialog
          open={selectedImageIndex !== null}
          onOpenChange={() => setSelectedImageIndex(null)}
        >
          <DialogContent className="max-w-[90vw] max-h-[90vh] p-0 overflow-hidden bg-black/90">
            <DialogHeader>
              <VisuallyHidden>
                <DialogTitle>Image Detail View</DialogTitle>
              </VisuallyHidden>
            </DialogHeader>
            <div className="relative w-full h-[90vh]">
              {selectedImageIndex !== null && (
                <>
                  <Image
                    src={photos[selectedImageIndex] ?? ''}
                    alt={`${listing.title} - Photo ${selectedImageIndex + 1}`}
                    fill
                    className="object-contain"
                    quality={100}
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    className="absolute top-4 right-4 bg-black/50 hover:bg-black/70 border-0 text-white"
                    onClick={() => setSelectedImageIndex(null)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="absolute left-4 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 border-0 text-white group"
                    onClick={handlePrevImage}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    <span className="sr-only">Previous image</span>
                    <span className="absolute left-full ml-2 px-2 py-1 bg-black/75 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      Press A or ←
                    </span>
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="absolute right-4 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 border-0 text-white group"
                    onClick={handleNextImage}
                  >
                    <ChevronRight className="h-4 w-4" />
                    <span className="sr-only">Next image</span>
                    <span className="absolute right-full mr-2 px-2 py-1 bg-black/75 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      Press D or →
                    </span>
                  </Button>
                  <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/50 text-white px-3 py-1.5 rounded-full">
                    {selectedImageIndex + 1} / {photos.length}
                  </div>
                </>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Wrap modal in Suspense */}
        <Suspense fallback={null}>
          {isComparisonModalOpen && (
            <ComparisonModal
              isOpen={isComparisonModalOpen}
              onClose={() => setIsComparisonModalOpen(false)}
              currentListing={listing}
              currentAnalysis={analysis}
              similarListings={similarListings}
              similarAnalyses={similarAnalyses}
              modelAnalytics={modelAnalytics}
            />
          )}
        </Suspense>
      </div>

      {/* Bug Report Modal */}
      <Suspense fallback={null}>
        {isBugReportModalOpen && (
          <BugReportModal
            isOpen={isBugReportModalOpen}
            onClose={() => setIsBugReportModalOpen(false)}
            listing={listing}
            analysis={analysis}
          />
        )}
      </Suspense>
    </div>
  );
}
