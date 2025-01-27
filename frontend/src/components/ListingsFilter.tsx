"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { FilterGroup } from "@/lib/types";
import AdvancedFilter from "./AdvancedFilter";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown } from "lucide-react";

export default function ListingsFilter() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState({
    price_min: searchParams.get("price_min") || "",
    price_max: searchParams.get("price_max") || "",
    search_text: searchParams.get("search_text") || "",
  });

  const [advancedFilter, setAdvancedFilter] = useState<FilterGroup | null>(
    () => {
      const advanced = searchParams.get("advanced");
      if (advanced) {
        try {
          const parsed = JSON.parse(advanced) as FilterGroup;
          return parsed?.conditions && parsed.conditions.length > 0
            ? parsed
            : null;
        } catch (e) {
          console.error("Failed to parse advanced filter:", e);
          return null;
        }
      }
      return null;
    }
  );

  const [isAdvancedOpen, setIsAdvancedOpen] = useState(() => {
    return searchParams.get("advanced") !== null;
  });

  // Sync state with URL params
  useEffect(() => {
    const price_min = searchParams.get("price_min") || "";
    const price_max = searchParams.get("price_max") || "";
    const search_text = searchParams.get("search_text") || "";
    const advanced = searchParams.get("advanced");

    setFilters({ price_min, price_max, search_text });

    if (advanced) {
      try {
        const parsed = JSON.parse(advanced) as FilterGroup;
        setAdvancedFilter(
          parsed?.conditions && parsed.conditions.length > 0 ? parsed : null
        );
        setIsAdvancedOpen(true);
      } catch (e) {
        console.error("Failed to parse advanced filter:", e);
        setAdvancedFilter(null);
      }
    } else {
      setAdvancedFilter(null);
    }
  }, [searchParams]);

  const handleFilter = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();

      const params = new URLSearchParams();

      // Only add non-empty values
      if (filters.price_min) params.set("price_min", filters.price_min);
      if (filters.price_max) params.set("price_max", filters.price_max);
      if (filters.search_text) params.set("search_text", filters.search_text);

      // Add advanced filter to URL as a JSON string
      if (advancedFilter?.conditions && advancedFilter.conditions.length > 0) {
        params.set("advanced", JSON.stringify(advancedFilter));
      }

      const queryString = params.toString();
      router.push(`/listings${queryString ? `?${queryString}` : ""}`, {
        scroll: false,
      });
    },
    [filters, advancedFilter, router]
  );

  const handleReset = useCallback(() => {
    setFilters({
      price_min: "",
      price_max: "",
      search_text: "",
    });
    setAdvancedFilter(null);
    setIsAdvancedOpen(false);
    router.push("/listings", { scroll: false });
  }, [router]);

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        handleFilter();
      }
    },
    [handleFilter]
  );

  const handleAdvancedFilterChange = useCallback(
    (filter: FilterGroup | null) => {
      setAdvancedFilter(filter);
      // Automatically apply filter when changed
      const params = new URLSearchParams(searchParams.toString());
      if (filter?.conditions && filter.conditions.length > 0) {
        params.set("advanced", JSON.stringify(filter));
      } else {
        params.delete("advanced");
      }
      router.push(`/listings?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  return (
    <div className="space-y-4">
      <form onSubmit={handleFilter} className="flex space-x-4">
        <Input
          type="number"
          placeholder="Min Price"
          value={filters.price_min}
          onChange={(e) =>
            setFilters({ ...filters, price_min: e.target.value })
          }
          onKeyDown={handleKeyPress}
        />
        <Input
          type="number"
          placeholder="Max Price"
          value={filters.price_max}
          onChange={(e) =>
            setFilters({ ...filters, price_max: e.target.value })
          }
          onKeyDown={handleKeyPress}
        />
        <Input
          type="text"
          placeholder="Search"
          value={filters.search_text}
          onChange={(e) =>
            setFilters({ ...filters, search_text: e.target.value })
          }
          onKeyDown={handleKeyPress}
        />
        <Button type="submit">Filter</Button>
        <Button type="button" variant="outline" onClick={handleReset}>
          Reset
        </Button>
      </form>

      <Collapsible
        open={isAdvancedOpen}
        onOpenChange={setIsAdvancedOpen}
        className="w-full mb-4"
      >
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-2"
          >
            Advanced Filters{" "}
            {advancedFilter?.conditions &&
              advancedFilter.conditions.length > 0 &&
              `(${advancedFilter.conditions.length} active)`}
            <ChevronDown
              className={`h-4 w-4 transition-transform ${
                isAdvancedOpen ? "transform rotate-180" : ""
              }`}
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className={isAdvancedOpen ? "mt-2" : ""}>
          <AdvancedFilter onFilterChange={handleAdvancedFilterChange} />
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
