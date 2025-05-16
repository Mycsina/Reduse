"use client";

import {
  useState,
  useEffect,
  useCallback,
  lazy,
  Suspense,
  useMemo,
} from "react";
import Image from "next/image";
import Link from "next/link";
import { ChevronLeft, ChevronRight, X, Flag } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "@/components/ui/visually-hidden";

import { formatPrice } from "@/lib/utils";
import { AnalysisStatus, AnalyzedListing } from "@/lib/api/admin/analysis";
import { Listing, ListingResponse } from "@/lib/api/query/query";
import {
  useInfiniteQuery,
  QueryKey,
  InfiniteData,
} from "@tanstack/react-query";
import { fetchSimilarListings } from "@/lib/api/query/query";
import ListingCard from "@/app/listings/ListingCard";

// Lazy load heavy components
const ComparisonModal = lazy(
  () => import("@/app/listings/[id]/ComparisonModal"),
);
const BugReportModal = lazy(() => import("@/app/listings/[id]/BugReportModal"));

interface ListingContentProps {
  listing: Listing;
  analysis: AnalyzedListing | null;
  initialSimilarListings: Listing[];
  initialSimilarAnalyses: AnalyzedListing[];
  listingId: string;
}

export default function ListingContent({
  listing,
  analysis,
  initialSimilarListings,
  initialSimilarAnalyses,
  listingId,
}: ListingContentProps) {
  const ITEMS_PER_PAGE = 10;

  const {
    data: similarData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isLoadingSimilar,
    status,
  } = useInfiniteQuery<
    ListingResponse[],
    Error,
    InfiniteData<ListingResponse[], number>,
    QueryKey,
    number
  >({
    queryKey: ["similarListings", listingId],
    queryFn: ({ pageParam = 0 }) =>
      fetchSimilarListings(
        listingId,
        pageParam * ITEMS_PER_PAGE,
        ITEMS_PER_PAGE,
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      return lastPage.length === ITEMS_PER_PAGE ? allPages.length : undefined;
    },
  });

  const allSimilarListings = useMemo(
    () =>
      similarData?.pages.flatMap((page: ListingResponse[]) =>
        page.map((item: ListingResponse) => item.listing),
      ) ?? initialSimilarListings,
    [similarData, initialSimilarListings],
  );

  const allSimilarAnalyses = useMemo(
    () =>
      similarData?.pages.flatMap(
        (page: ListingResponse[]) =>
          page
            .map((item: ListingResponse) => item.analysis)
            .filter(Boolean) as AnalyzedListing[],
      ) ?? initialSimilarAnalyses,
    [similarData, initialSimilarAnalyses],
  );

  const [isComparisonModalOpen, setIsComparisonModalOpen] = useState(false);
  const [isBugReportModalOpen, setIsBugReportModalOpen] = useState(false);
  const [currentImageGroup, setCurrentImageGroup] = useState(0);
  const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(
    null,
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
    (currentImageGroup + 1) * groupSize,
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
      selectedImageIndex === 0 ? photos.length - 1 : selectedImageIndex - 1,
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

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (isComparisonModalOpen) return;
      if (isBugReportModalOpen) return;

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
    },
    [
      isComparisonModalOpen,
      selectedImageIndex,
      handlePrevImage,
      handleNextImage,
      numGroups,
      handlePrevGroup,
      handleNextGroup,
    ],
  );

  // Add keyboard event listener only when the modal is closed
  useEffect(() => {
    if (!isBugReportModalOpen && !isComparisonModalOpen) {
      window.addEventListener("keydown", handleKeyDown);
      return () => {
        window.removeEventListener("keydown", handleKeyDown);
      };
    }
    // If a modal is open, ensure any existing listener is removed
    // (This handles cases where the modal opens while listener is active)
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleKeyDown, isBugReportModalOpen, isComparisonModalOpen]); // Add modal states to dependencies

  // Function to fetch the next batch of listings
  const fetchNextBatch = useCallback(async () => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Effect to handle intersection observer for loading more
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.5 },
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
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Use a grid layout, splitting 2/5 for photos and 3/5 for details on medium screens and up */}
      <div className="grid grid-cols-1 gap-8 md:grid-cols-5">
        {/* Left Column: Photos (Sticky) */}
        <div className="h-fit md:sticky md:top-8 md:col-span-2">
          {" "}
          {/* Use h-fit to prevent sticky element stretching */}
          <Card className="overflow-hidden">
            {/* Photos section */}
            <div className="bg-muted relative">
              <div className="relative">
                <div className="grid aspect-[4/3] grid-cols-2 gap-2">
                  {currentPhotos.map((url, index) => (
                    <div
                      key={index}
                      className={`relative ${
                        currentPhotos.length === 1
                          ? "col-span-2 row-span-2" // Full size if only 1 photo
                          : currentPhotos.length === 2
                            ? "col-span-1 row-span-2" // Half width if 2 photos
                            : currentPhotos.length === 3 && index === 0
                              ? "col-span-2" // First photo takes full width if 3 photos
                              : "" // Default: square grid item
                      } group aspect-square cursor-pointer`} // Ensure aspect ratio for grid items
                      onClick={() => handleImageClick(currentImageGroup, index)}
                    >
                      <Image
                        src={url ?? ""}
                        alt={`${listing.title} - Photo ${currentImageGroup * groupSize + index + 1}`}
                        fill
                        className="rounded-lg object-cover transition-opacity group-hover:opacity-90"
                        sizes="(max-width: 768px) 50vw, (max-width: 1024px) 20vw, 400px" // Add sizes for better performance
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
                      className="group absolute top-1/2 left-2 z-10 -translate-y-1/2 bg-white/80 hover:bg-white" // Ensure buttons are above images
                      onClick={handlePrevGroup}
                      aria-label="Previous image group"
                    >
                      <ChevronLeft className="h-4 w-4" />
                      <span className="sr-only">Previous group</span>
                      <span className="absolute left-full ml-2 rounded bg-black/75 px-2 py-1 text-xs whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
                        Press A or ←
                      </span>
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      className="group absolute top-1/2 right-2 z-10 -translate-y-1/2 bg-white/80 hover:bg-white" // Ensure buttons are above images
                      onClick={handleNextGroup}
                      aria-label="Next image group"
                    >
                      <ChevronRight className="h-4 w-4" />
                      <span className="sr-only">Next group</span>
                      <span className="absolute right-full mr-2 rounded bg-black/75 px-2 py-1 text-xs whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
                        Press D or →
                      </span>
                    </Button>
                    {/* Group Indicator */}
                    <div className="absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/50 px-2 py-1 text-sm text-white">
                      {currentImageGroup + 1} / {numGroups}
                    </div>
                  </>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Details and Analysis (Scrollable) */}
        <div className="space-y-6 md:col-span-3">
          {/* Listing details Card */}
          <Card className="overflow-hidden">
            <div className="p-6">
              <div className="mb-4 flex items-start justify-between">
                <h1 className="text-2xl font-bold">{listing.title}</h1>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsBugReportModalOpen(true)}
                  className="text-muted-foreground hover:text-foreground flex items-center gap-1"
                  aria-label="Report issue with listing"
                >
                  <Flag className="h-4 w-4" />
                  <span>Report</span>
                </Button>
              </div>

              <div>
                <p className="text-primary mb-4 text-3xl font-bold">
                  {formatPrice(listing.price_value ? listing.price_value : 0)}
                </p>
              </div>

              <div>
                <h2 className="mb-2 text-lg font-semibold">Description</h2>
                <p className="text-muted-foreground whitespace-pre-wrap">
                  {listing.description}
                </p>
              </div>
            </div>
          </Card>

          {/* Analysis Information Card */}
          <Card className="p-6">
            <h2 className="mb-4 text-xl font-semibold">Analysis Details</h2>
            {listing.analysis_status === AnalysisStatus.COMPLETED &&
            analysis ? (
              <div className="space-y-4">
                {/* Analysis fields */}
                <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                  <div>
                    <label className="text-muted-foreground block text-sm">
                      Type
                    </label>
                    <p className="font-medium">{analysis.type || "N/A"}</p>
                  </div>
                  <div>
                    <label className="text-muted-foreground block text-sm">
                      Brand
                    </label>
                    <p className="font-medium">{analysis.brand || "N/A"}</p>
                  </div>
                  <div>
                    <label className="text-muted-foreground block text-sm">
                      Base Model
                    </label>
                    <p className="font-medium">
                      {analysis.base_model || "N/A"}
                    </p>
                  </div>
                  <div>
                    <label className="text-muted-foreground block text-sm">
                      Model Variant
                    </label>
                    <p className="font-medium">
                      {analysis.model_variant || "N/A"}
                    </p>
                  </div>
                </div>
                {/* Additional analyzed info */}
                {analysis.info && Object.keys(analysis.info).length > 0 && (
                  <>
                    <hr className="my-4" />
                    <h3 className="text-md mb-2 font-semibold">
                      Additional Details
                    </h3>
                    <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                      {Object.entries(analysis.info || {}).map(
                        ([key, value]) => (
                          <div key={key}>
                            <label className="text-muted-foreground block text-sm capitalize">
                              {key.replace(/_/g, " ")}
                            </label>
                            <p className="font-medium">{String(value)}</p>
                          </div>
                        ),
                      )}
                    </div>
                  </>
                )}
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
            allSimilarListings.length > 0 &&
            allSimilarAnalyses.length > 0 && (
              <div className="space-y-2">
                <Button
                  className="w-full"
                  onClick={() => setIsComparisonModalOpen(true)}
                >
                  Quick Compare Similar Listings
                </Button>
                <Link href={`/comparison/${listing._id}`} className="block">
                  {" "}
                  {/* Ensure Link takes full width */}
                  <Button className="w-full" variant="outline">
                    Detailed Comparison Page
                  </Button>
                </Link>
              </div>
            )}
        </div>
      </div>

      {/* Similar Listings Section */}
      <section className="mt-12">
        <h2 className="mb-6 text-2xl font-semibold">Similar Listings</h2>
        {isLoadingSimilar && allSimilarListings.length === 0 && (
          <div className="text-center">
            <p>Loading similar listings...</p>
            {/* Optional: Add a spinner component */}
          </div>
        )}
        {!isLoadingSimilar && allSimilarListings.length === 0 && (
          <div className="text-center">
            <p>No similar listings found.</p>
          </div>
        )}
        {allSimilarListings.length > 0 && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {allSimilarListings.map((simListing: Listing) => {
              const simAnalysis = allSimilarAnalyses.find(
                (a: AnalyzedListing) =>
                  a.original_listing_id === simListing.original_id,
              );
              return (
                <ListingCard
                  key={simListing._id || simListing.original_id} // Use original_id as fallback key
                  listing={simListing}
                  analysis={simAnalysis || null}
                />
              );
            })}
          </div>
        )}
        {/* Load More Trigger for Intersection Observer and Fallback Button */}
        {hasNextPage && (
          <div id="load-more-trigger" className="mt-8 flex justify-center">
            <Button
              onClick={() => fetchNextPage()}
              disabled={isFetchingNextPage}
            >
              {isFetchingNextPage
                ? "Loading more..."
                : "Load More Similar Listings"}
            </Button>
          </div>
        )}
      </section>

      {/* Image Detail Modal */}
      <Dialog
        open={selectedImageIndex !== null}
        onOpenChange={(isOpen) => !isOpen && setSelectedImageIndex(null)} // Close only when explicitly closed
      >
        <DialogContent className="max-h-[90vh] max-w-[90vw] overflow-hidden border-none bg-black/90 p-0">
          <DialogHeader>
            <VisuallyHidden>
              <DialogTitle>Image Detail View</DialogTitle>
            </VisuallyHidden>
            {/* Close button inside header for better positioning */}
            <Button
              variant="ghost" // Use ghost for less visual clutter
              size="icon"
              className="absolute top-2 right-2 z-50 h-8 w-8 rounded-full bg-black/30 text-white hover:bg-black/50"
              onClick={() => setSelectedImageIndex(null)}
              aria-label="Close image viewer"
            >
              <X className="h-4 w-4" />
            </Button>
          </DialogHeader>
          <div className="relative h-[calc(90vh-4rem)] w-full">
            {" "}
            {/* Adjust height based on potential header */}
            {selectedImageIndex !== null &&
              photos[selectedImageIndex] && ( // Check if photo URL exists
                <>
                  <Image
                    src={photos[selectedImageIndex] ?? ""}
                    alt={`${listing.title} - Photo ${selectedImageIndex + 1}`}
                    fill
                    className="object-contain"
                    quality={100} // High quality for detail view
                    sizes="90vw"
                  />
                  {/* Prev/Next Buttons */}
                  <Button
                    variant="outline"
                    size="icon"
                    className="group absolute top-1/2 left-4 h-10 w-10 -translate-y-1/2 rounded-full border-0 bg-black/50 text-white hover:bg-black/70"
                    onClick={handlePrevImage}
                    aria-label="Previous image"
                  >
                    <ChevronLeft className="h-5 w-5" />
                    <span className="sr-only">Previous image</span>
                    <span className="absolute left-full ml-2 rounded bg-black/75 px-2 py-1 text-xs whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
                      Press A or ←
                    </span>
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="group absolute top-1/2 right-4 h-10 w-10 -translate-y-1/2 rounded-full border-0 bg-black/50 text-white hover:bg-black/70"
                    onClick={handleNextImage}
                    aria-label="Next image"
                  >
                    <ChevronRight className="h-5 w-5" />
                    <span className="sr-only">Next image</span>
                    <span className="absolute right-full mr-2 rounded bg-black/75 px-2 py-1 text-xs whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
                      Press D or →
                    </span>
                  </Button>
                  {/* Counter */}
                  <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-3 py-1.5 text-sm text-white">
                    {selectedImageIndex + 1} / {photos.length}
                  </div>
                </>
              )}
            {selectedImageIndex !== null && !photos[selectedImageIndex] && (
              <div className="absolute inset-0 flex items-center justify-center text-white">
                Error loading image.
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Comparison Modal */}
      <Suspense fallback={<div>Loading comparison...</div>}>
        {" "}
        {/* Provide fallback */}
        {isComparisonModalOpen && (
          <ComparisonModal
            isOpen={isComparisonModalOpen}
            onClose={() => setIsComparisonModalOpen(false)}
            currentListing={listing}
            currentAnalysis={analysis}
            similarListings={allSimilarListings}
            similarAnalyses={allSimilarAnalyses}
          />
        )}
      </Suspense>

      {/* Bug Report Modal */}
      <Suspense fallback={<div>Loading report form...</div>}>
        {/* Provide fallback */}
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
