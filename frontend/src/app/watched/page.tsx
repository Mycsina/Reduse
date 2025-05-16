"use client";

import React from "react";
import { useFavoriteSearches } from "@/hooks/useFavorites";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trash2, Edit, Eye, LogIn } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import type { FavoriteSearchRead } from "@/lib/api/favorites";
import { useAuth } from "@/providers/AuthProvider";

export default function WatchedSearchesPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: isLoadingAuth } = useAuth();

  // Fetch favorites only if authenticated
  const {
    favorites,
    isLoading: isLoadingFavorites,
    removeFavorite,
    updateFavorite,
  } = useFavoriteSearches(isAuthenticated);

  const { toast } = useToast();

  // TODO: Implement a way to fetch new listing counts efficiently
  // Maybe a separate endpoint or calculate based on getFavoriteListingsSplit?
  // For now, we'll just show the link.

  const handleView = (favoriteId: string) => {
    // Find the favorite search data
    const favorite = favorites?.find(
      (f: FavoriteSearchRead) => f._id === favoriteId,
    );
    if (!favorite) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Could not find favorite search details.",
      });
      return;
    }

    // Build URL search params from the favorite's query
    const params = new URLSearchParams();
    const query = favorite.query_params;

    if (query.price?.min !== undefined)
      params.set("price_min", query.price.min.toString());
    if (query.price?.max !== undefined)
      params.set("price_max", query.price.max.toString());
    if (query.search_text) params.set("search_text", query.search_text);
    if (query.filter) params.set("advanced", JSON.stringify(query.filter));

    // Navigate to listings page with standard filter parameters
    router.push(`/listings?${params.toString()}`);
  };

  const handleDelete = async (favoriteId: string, name: string) => {
    if (
      confirm(`Are you sure you want to delete the favorite search "${name}"?`)
    ) {
      try {
        await removeFavorite(favoriteId);
      } catch (error) {
        // Error handled by hook
      }
    }
  };

  const handleRename = async (favoriteId: string, currentName: string) => {
    const newName = prompt(
      "Enter a new name for this favorite search:",
      currentName,
    );
    if (newName && newName !== currentName) {
      try {
        await updateFavorite({ id: favoriteId, data: { name: newName } });
      } catch (error) {
        // Error handled by hook
      }
    }
  };

  // Loading state for auth or favorites
  if (isLoadingAuth || (isAuthenticated && isLoadingFavorites)) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="mb-6 text-3xl font-bold">Watched Searches</h1>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="mt-2 h-4 w-1/2" />
              </CardHeader>
              <CardContent className="flex justify-end space-x-2">
                <Skeleton className="h-8 w-8 rounded-full" />
                <Skeleton className="h-8 w-8 rounded-full" />
                <Skeleton className="h-8 w-8 rounded-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Not authenticated state
  if (!isAuthenticated) {
    return (
      <div className="container mx-auto flex h-[60vh] flex-col items-center justify-center px-4 py-8 text-center">
        <h1 className="mb-4 text-3xl font-bold">Watched Searches</h1>
        <p className="text-muted-foreground mb-6 text-lg">
          You need to be logged in to save and view favorite searches.
        </p>
        <Button asChild>
          <Link href="/login">
            <LogIn className="mr-2 h-4 w-4" /> Login or Sign Up
          </Link>
        </Button>
      </div>
    );
  }

  // Authenticated but no favorites state
  if (!favorites || favorites.length === 0) {
    return (
      <div className="container mx-auto px-4 py-8 text-center">
        <h1 className="mb-6 text-3xl font-bold">Watched Searches</h1>
        <p>You haven't saved any searches yet.</p>
        <Button asChild className="mt-4">
          <Link href="/listings">Explore Listings</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="mb-6 text-3xl font-bold">Watched Searches</h1>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {favorites.map((fav: FavoriteSearchRead) => (
          <Card key={fav._id}>
            <CardHeader>
              <CardTitle className="truncate">{fav.name}</CardTitle>
              <CardDescription>
                Saved: {new Date(fav.created_at).toLocaleDateString()}
                {fav.last_viewed_at && (
                  <span className="block text-xs">
                    Last viewed: {new Date(fav.last_viewed_at).toLocaleString()}
                  </span>
                )}
              </CardDescription>
              {fav.new_listings_count > 0 && (
                <p className="mt-1 text-sm font-medium text-green-600">
                  {fav.new_listings_count} new listing
                  {fav.new_listings_count > 1 ? "s" : ""}
                </p>
              )}
            </CardHeader>
            <CardContent className="flex justify-end space-x-2">
              <Button
                variant="outline"
                size="icon"
                onClick={() => handleView(fav._id)}
                aria-label="View Listings"
              >
                <Eye className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => handleRename(fav._id, fav.name)}
                aria-label="Rename Search"
              >
                <Edit className="h-4 w-4" />
              </Button>
              <Button
                variant="destructive"
                size="icon"
                onClick={() => handleDelete(fav._id, fav.name)}
                aria-label="Delete Search"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
