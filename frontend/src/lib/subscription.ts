import { apiClient } from "./api-client";
import { toast } from "@/hooks/use-toast";

interface SubscriptionCheckResult {
  canAccess: boolean;
  error?: string;
}

/**
 * Check if a user can access a premium feature based on their subscription status
 * or remaining usage limits.
 */
export async function checkFeatureAccess(
  feature: string,
  isPremium: boolean
): Promise<SubscriptionCheckResult> {
  if (isPremium) {
    return { canAccess: true };
  }

  try {
    const usage = await apiClient.getFeatureUsage(feature);
    
    if (usage.remaining <= 0) {
      return {
        canAccess: false,
        error: "Usage limit reached. Please upgrade to continue.",
      };
    }

    return { canAccess: true };
  } catch (error) {
    console.error(`Failed to check feature access for ${feature}:`, error);
    return {
      canAccess: false,
      error: "Failed to verify feature access. Please try again.",
    };
  }
}

/**
 * Record usage of a feature for non-premium users.
 * Returns true if usage was successfully recorded, false otherwise.
 */
export async function recordFeatureUsage(
  feature: string,
  isPremium: boolean
): Promise<boolean> {
  if (isPremium) {
    return true;
  }

  try {
    await apiClient.recordFeatureUsage(feature);
    return true;
  } catch (error) {
    console.error(`Failed to record usage for ${feature}:`, error);
    
    // Show error toast only if it's not a usage limit error (402)
    if (error instanceof Error && !error.message.includes("402")) {
      toast({
        title: "Error",
        description: "Failed to record feature usage",
        variant: "destructive",
      });
    }
    
    return false;
  }
}

/**
 * Handle subscription-related errors and show appropriate UI feedback.
 */
export function handleSubscriptionError(error: unknown): string {
  if (error instanceof Error) {
    if (error.message.includes("402")) {
      return "Usage limit reached. Please upgrade to continue.";
    }
    if (error.message.includes("401")) {
      return "Please sign in to access this feature.";
    }
    if (error.message.includes("403")) {
      return "You don't have permission to access this feature.";
    }
  }
  return "An error occurred. Please try again.";
}

/**
 * Redirect to the subscription page with an optional return URL.
 */
export function redirectToUpgrade(returnUrl?: string) {
  const url = new URL("/subscription", window.location.origin);
  if (returnUrl) {
    url.searchParams.set("returnUrl", returnUrl);
  }
  window.location.href = url.toString();
} 