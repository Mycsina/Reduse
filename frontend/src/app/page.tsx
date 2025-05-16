"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { useNaturalLanguageQueryMutation } from "@/lib/api/query/query";
import type { ListingQuery } from "@/lib/api/query/query";

export default function Home() {
  const [query, setQuery] = useState("");
  const router = useRouter();
  const { toast } = useToast();

  const processNLQMutation = useNaturalLanguageQueryMutation();

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      const structuredQuery: ListingQuery =
        await processNLQMutation.mutateAsync(query);

      const params = new URLSearchParams();

      if (structuredQuery.search_text) {
        params.set("search_text", structuredQuery.search_text);
      }
      if (structuredQuery.price) {
        if (
          structuredQuery.price.min !== undefined &&
          structuredQuery.price.min !== null
        ) {
          params.set("price_min", structuredQuery.price.min.toString());
        }
        if (
          structuredQuery.price.max !== undefined &&
          structuredQuery.price.max !== null
        ) {
          params.set("price_max", structuredQuery.price.max.toString());
        }
      }
      if (
        structuredQuery.filter &&
        structuredQuery.filter.conditions.length > 0
      ) {
        params.set("advanced", JSON.stringify(structuredQuery.filter));
      }

      router.push(`/listings?${params.toString()}`);
    } catch (error: any) {
      console.error("Search error on page:", error);
      if (!processNLQMutation.isError) {
        toast({
          title: "Search failed",
          description:
            error.message || "There was an error processing your query.",
          variant: "destructive",
        });
      }
    }
  }

  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="mb-8 text-center text-4xl font-bold">
        Find Your Next Deal with Natural Language
      </h1>

      <div className="mx-auto mb-12 max-w-2xl">
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Try 'Apartments under $500,000 with at least 2 bedrooms' or 'Red cars with low mileage'"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1"
          />
          <Button type="submit" disabled={processNLQMutation.isPending}>
            {processNLQMutation.isPending ? "Searching..." : "Search"}
          </Button>
        </form>

        <div className="mt-2 text-sm text-gray-500">
          Ask in plain language what you&apos;re looking for, and our AI will
          find it.
        </div>
      </div>
    </main>
  );
}
