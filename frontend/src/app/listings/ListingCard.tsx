import Link from "next/link";
import { Card } from "@/components/ui/card";
import type { Listing } from "@/lib/api/query/query";
import type { AnalyzedListingDocument } from "@/lib/api/admin/analysis";
import Image from "next/image";
import { ImageOff } from "lucide-react";

interface ListingCardProps {
  listing: Listing;
  analysis?: AnalyzedListingDocument | null;
  favoriteId?: string;
}

export default function ListingCard({
  listing,
  analysis,
  favoriteId,
}: ListingCardProps) {
  const hasPhoto = listing.photo_urls && listing.photo_urls.length > 0;

  const displayModel = analysis
    ? `${analysis.brand} ${analysis.base_model}`
    : listing.site;

  const linkHref = favoriteId
    ? `/listings/${listing._id}?favoriteId=${favoriteId}`
    : `/listings/${listing._id}`;

  return (
    <Link key={listing._id} href={linkHref}>
      <Card className="transition-shadow hover:shadow-lg">
        <div className="bg-muted relative h-48 w-full">
          {hasPhoto ? (
            <Image
              src={(listing.photo_urls ?? [""])[0]}
              alt={listing.title}
              fill
              className="rounded-t-lg object-cover"
              loading="lazy"
              sizes="(max-width: 640px) 100vw, (max-width: 768px) 50vw, (max-width: 1024px) 33vw, 25vw"
              quality={75}
            />
          ) : (
            <div className="text-muted-foreground absolute inset-0 flex items-center justify-center">
              <ImageOff className="h-8 w-8" />
            </div>
          )}
        </div>
        <div className="flex flex-grow flex-col p-4">
          <h3 className="mb-1 truncate font-semibold" title={listing.title}>
            {listing.title}
          </h3>
          {analysis && (
            <p
              className="mb-1 truncate text-xs text-blue-600"
              title={`${analysis.brand} ${analysis.base_model} ${analysis.model_variant || ""}`}
            >
              {analysis.brand} {analysis.base_model} {analysis.model_variant}
            </p>
          )}
          <p className="text-primary mt-auto pt-2 text-lg font-bold">
            {listing.price_str + "€" ||
              (listing.price_value
                ? `€${listing.price_value}`
                : "Price unavailable")}
          </p>
          <p className="text-muted-foreground truncate text-xs">
            {listing.site}
          </p>
        </div>
      </Card>
    </Link>
  );
}
