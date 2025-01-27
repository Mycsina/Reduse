"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ListingsGrid from "@/components/ListingsGrid";
import ListingsFilter from "@/components/ListingsFilter";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterGroup } from "@/lib/types";

export default function ListingsPage() {
  const searchParams = useSearchParams();

  const filters = {
    price_min: searchParams.get("price_min")
      ? Number(searchParams.get("price_min"))
      : undefined,
    price_max: searchParams.get("price_max")
      ? Number(searchParams.get("price_max"))
      : undefined,
    search_text: searchParams.get("search_text") || undefined,
    advanced: searchParams.get("advanced")
      ? (JSON.parse(searchParams.get("advanced")!) as FilterGroup)
      : undefined,
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Listings</h1>
      <ListingsFilter />
      <Suspense fallback={<Skeleton className="h-[200px]" />}>
        <ListingsGrid filters={filters} />
      </Suspense>
    </div>
  );
}
