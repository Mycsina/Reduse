import Link from "next/link";
import { Card } from "./ui/card";
import { Listing } from "@/lib/types";
import Image from "next/image";
import { ImageOff } from "lucide-react";

export default function ListingCard({ listing }: { listing: Listing }) {
  const hasPhoto = listing.photo_urls?.length > 0;

  return (
    <Link key={listing._id} href={`/listings/${listing._id}`}>
      <Card className="hover:shadow-lg transition-shadow">
        <div className="relative h-48 w-full bg-muted">
          {hasPhoto ? (
            <Image
              src={listing.photo_urls[0]}
              alt={listing.title}
              fill
              className="object-cover rounded-t-lg"
              loading="lazy"
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
              quality={75}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
              <ImageOff className="h-8 w-8" />
            </div>
          )}
        </div>
        <div className="p-4">
          <h3 className="font-semibold truncate">{listing.title}</h3>
          <p className="text-sm text-muted-foreground">{listing._id}</p>
          <p className="text-lg font-bold text-primary">
            €{listing.price_value}
          </p>
          <p className="text-sm text-muted-foreground">{listing.site}</p>
        </div>
      </Card>
    </Link>
  );
}
