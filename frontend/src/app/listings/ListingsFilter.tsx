"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useCallback, useEffect, useMemo } from "react";
import { FilterGroup, ListingQuery, PriceRange } from "@/lib/api/query/query";
import AdvancedFilter from "./AdvancedFilter";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown } from "lucide-react";

import { ResolvedFilters } from "@/app/listings/page";
import { useFavoriteStatus, useFavoriteSearches } from "@/hooks/useFavorites";
import FavoriteButton from "@/components/ui/checkmarkButton";
import { toast } from "@/hooks/use-toast";
import { useAuth } from "@/providers/AuthProvider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Label } from "@/components/ui/label";

interface ListingsFilterProps {
  initialFilters?: ResolvedFilters;
}

export default function ListingsFilter({
  initialFilters,
}: ListingsFilterProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuth();

  const [filters, setFilters] = useState({
    price_min: initialFilters?.price_min?.toString() || "",
    price_max: initialFilters?.price_max?.toString() || "",
    search_text: initialFilters?.search_text || "",
  });

  const [advancedFilter, setAdvancedFilter] = useState<FilterGroup | null>(
    initialFilters?.advanced || null,
  );

  const [isAdvancedOpen, setIsAdvancedOpen] = useState(() => {
    return !!initialFilters?.advanced?.conditions?.length;
  });

  const [isNamingFavoriteOpen, setIsNamingFavoriteOpen] = useState(false);
  const [favoriteName, setFavoriteName] = useState("");

  const currentQuery = useMemo((): ListingQuery | null => {
    const price: PriceRange | undefined =
      filters.price_min || filters.price_max
        ? {
            min: filters.price_min ? Number(filters.price_min) : undefined,
            max: filters.price_max ? Number(filters.price_max) : undefined,
          }
        : undefined;

    if (
      !price &&
      !filters.search_text &&
      (!advancedFilter || advancedFilter.conditions.length === 0)
    ) {
      return null;
    }

    return {
      price: price,
      search_text: filters.search_text || undefined,
      filter:
        (advancedFilter?.conditions?.length ?? 0) > 0
          ? advancedFilter!
          : undefined,
    };
  }, [filters, advancedFilter]);

  const { isFavorite, favoriteId, isLoadingFavorites } = useFavoriteStatus(
    currentQuery,
    isAuthenticated,
  );
  const { addFavorite, removeFavorite } = useFavoriteSearches(isAuthenticated);

  const handleFilter = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();

      const params = new URLSearchParams(searchParams);

      if (filters.price_min) params.set("price_min", filters.price_min);
      else params.delete("price_min");
      if (filters.price_max) params.set("price_max", filters.price_max);
      else params.delete("price_max");
      if (filters.search_text) params.set("search_text", filters.search_text);
      else params.delete("search_text");

      if (advancedFilter?.conditions && advancedFilter.conditions.length > 0) {
        params.set("advanced", JSON.stringify(advancedFilter));
      } else {
        params.delete("advanced");
      }

      const queryString = params.toString();
      router.push(`/listings${queryString ? `?${queryString}` : ""}`, {
        scroll: false,
      });
    },
    [filters, advancedFilter, router, searchParams],
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
    [handleFilter],
  );

  const handleAdvancedFilterChange = useCallback(
    (filter: FilterGroup | null) => {
      setAdvancedFilter(filter);
    },
    [],
  );

  useEffect(() => {
    handleFilter();
  }, [advancedFilter, handleFilter]);

  const handleFavoriteToggle = useCallback(async () => {
    if (!isAuthenticated) {
      toast({
        variant: "default",
        title: "Login Required",
        description: "Please log in to manage favorite searches.",
      });
      return;
    }

    if (isLoadingFavorites) return;

    if (isFavorite && favoriteId) {
      await removeFavorite(favoriteId);
    } else if (currentQuery) {
      setFavoriteName(""); // Reset name for new favorite
      setIsNamingFavoriteOpen(true); // Open popover to name it
    } else {
      toast({
        title: "Cannot save an empty search as favorite.",
      });
    }
  }, [
    isAuthenticated,
    isFavorite,
    favoriteId,
    currentQuery,
    removeFavorite,
    isLoadingFavorites,
    toast,
    setIsNamingFavoriteOpen,
  ]);

  const handleSaveFavoriteName = useCallback(async () => {
    if (!currentQuery) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "No active query to save.",
      });
      return;
    }
    if (!favoriteName.trim()) {
      toast({
        variant: "destructive",
        title: "Name Required",
        description: "Please enter a name for your favorite search.",
      });
      return;
    }
    try {
      await addFavorite({ name: favoriteName, query_params: currentQuery });
      setIsNamingFavoriteOpen(false);
      // favoriteName will be reset when popover opens next time or can be reset here too
    } catch (err) {
      // Error handled by hook mutation, or add toast here if needed
      toast({
        variant: "destructive",
        title: "Error Saving Favorite",
        description:
          err instanceof Error
            ? err.message
            : "Could not save favorite search.",
      });
    }
  }, [favoriteName, currentQuery, addFavorite, setIsNamingFavoriteOpen, toast]);

  return (
    <div className="mb-6 space-y-4">
      <form
        onSubmit={handleFilter}
        className="grid grid-cols-1 items-end gap-4 md:grid-cols-5"
      >
        <div className="flex flex-col space-y-1">
          <label
            htmlFor="min-price"
            className="text-sm font-medium text-gray-700"
          >
            Min Price
          </label>
          <Input
            id="min-price"
            type="number"
            placeholder="Any"
            value={filters.price_min}
            onChange={(e) =>
              setFilters({ ...filters, price_min: e.target.value })
            }
            onKeyDown={handleKeyPress}
            className="h-10"
          />
        </div>
        <div className="flex flex-col space-y-1">
          <label
            htmlFor="max-price"
            className="text-sm font-medium text-gray-700"
          >
            Max Price
          </label>
          <Input
            id="max-price"
            type="number"
            placeholder="Any"
            value={filters.price_max}
            onChange={(e) =>
              setFilters({ ...filters, price_max: e.target.value })
            }
            onKeyDown={handleKeyPress}
            className="h-10"
          />
        </div>
        <div className="flex flex-col space-y-1 md:col-span-2">
          <label
            htmlFor="search-text"
            className="text-sm font-medium text-gray-700"
          >
            Search Text
          </label>
          <Input
            id="search-text"
            type="text"
            placeholder="Keywords..."
            value={filters.search_text}
            onChange={(e) =>
              setFilters({ ...filters, search_text: e.target.value })
            }
            onKeyDown={handleKeyPress}
            className="h-10"
          />
        </div>
        <div className="flex space-x-2">
          <Button type="submit" className="h-10 flex-grow">
            Filter
          </Button>

          <Popover
            open={isNamingFavoriteOpen}
            onOpenChange={setIsNamingFavoriteOpen}
          >
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <PopoverTrigger asChild>
                  <TooltipTrigger asChild>
                    <span tabIndex={!isAuthenticated ? 0 : undefined}>
                      <FavoriteButton
                        onClick={handleFavoriteToggle}
                        isFavorite={isAuthenticated && isFavorite}
                        className="h-10"
                        aria-label={
                          isFavorite
                            ? "Remove from favorites"
                            : "Add to favorites"
                        }
                        disabled={!isAuthenticated || isLoadingFavorites}
                      />
                    </span>
                  </TooltipTrigger>
                </PopoverTrigger>
                {!isAuthenticated && (
                  <TooltipContent>
                    <p>Login to save favorites</p>
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
            <PopoverContent className="w-80">
              <div className="grid gap-4">
                <div className="space-y-2">
                  <h4 className="leading-none font-medium">Name your search</h4>
                  <p className="text-muted-foreground text-sm">
                    Enter a name to save this search to your favorites.
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="favorite-name">Name</Label>
                  <Input
                    id="favorite-name"
                    value={favoriteName}
                    onChange={(e) => setFavoriteName(e.target.value)}
                    placeholder="e.g., My Dream Bike"
                    onKeyDown={(e) =>
                      e.key === "Enter" && handleSaveFavoriteName()
                    }
                  />
                  <Button onClick={handleSaveFavoriteName}>
                    Save Favorite
                  </Button>
                </div>
              </div>
            </PopoverContent>
          </Popover>

          <Button
            type="button"
            variant="outline"
            onClick={handleReset}
            className="h-10 flex-grow"
          >
            Reset
          </Button>
        </div>
      </form>

      <Collapsible
        open={isAdvancedOpen}
        onOpenChange={setIsAdvancedOpen}
        className="w-full rounded-md border p-2"
      >
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="flex w-full items-center justify-between p-2 hover:bg-gray-100"
          >
            <span className="font-semibold">
              Advanced Filters{" "}
              {advancedFilter?.conditions &&
                advancedFilter.conditions.length > 0 && (
                  <span className="text-sm font-normal text-gray-600">{`(${advancedFilter.conditions.length} active)`}</span>
                )}
            </span>
            <ChevronDown
              className={`h-5 w-5 transition-transform ${
                isAdvancedOpen ? "rotate-180 transform" : ""
              }`}
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="px-2 pt-4">
          <AdvancedFilter
            initialFilterGroup={advancedFilter}
            onFilterChange={handleAdvancedFilterChange}
          />
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
