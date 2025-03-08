"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { loadStripe } from "@stripe/stripe-js";
import { useSession } from "next-auth/react";

interface Subscription {
  status: string;
  currentPeriodEnd: string;
  stripeCustomerId: string;
  stripeSubscriptionId?: string;
}

export default function SubscriptionPage() {
  const { data: session } = useSession();
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const fetchSubscription = async () => {
      if (!session?.user?.id) return;

      try {
        const response = await fetch(
          `/api/payments/subscription-status/${session.user.id}`
        );
        if (!response.ok)
          throw new Error("Failed to fetch subscription status");
        const data = await response.json();
        setSubscription(data);
      } catch (error) {
        console.error("Error fetching subscription:", error);
        toast({
          title: "Error",
          description: "Failed to load subscription status",
          variant: "destructive",
        });
      }
    };

    fetchSubscription();
  }, [session, toast]);

  const handleSubscribe = async () => {
    if (!session?.user?.id) {
      toast({
        title: "Error",
        description: "Please sign in to subscribe",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/payments/create-checkout-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ userId: session.user.id }),
      });

      if (!response.ok) throw new Error("Failed to create checkout session");

      const { sessionId } = await response.json();
      const stripe = await loadStripe(
        process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!
      );

      if (!stripe) {
        throw new Error("Stripe failed to load");
      }

      await stripe.redirectToCheckout({ sessionId });
    } catch (error) {
      console.error("Error creating checkout session:", error);
      toast({
        title: "Error",
        description: "Failed to start checkout process",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container max-w-4xl mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-8">Premium Subscription</h1>

      <Card className="p-6 mb-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h2 className="text-2xl font-semibold mb-2">€3/month</h2>
            <ul className="space-y-2 mb-4 md:mb-0">
              <li className="flex items-center">
                <CheckIcon className="mr-2 h-5 w-5 text-green-500" />
                Full access to model price history
              </li>
              <li className="flex items-center">
                <CheckIcon className="mr-2 h-5 w-5 text-green-500" />
                Detailed price analytics
              </li>
              <li className="flex items-center">
                <CheckIcon className="mr-2 h-5 w-5 text-green-500" />
                Price trend notifications
              </li>
            </ul>
          </div>

          <Button
            onClick={handleSubscribe}
            disabled={loading || subscription?.status === "active"}
            className="w-full md:w-auto"
          >
            {loading ? (
              <>
                <LoaderIcon className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : subscription?.status === "active" ? (
              "Current Plan"
            ) : (
              "Subscribe Now"
            )}
          </Button>
        </div>
      </Card>

      {subscription && (
        <Card className="p-6">
          <h3 className="font-semibold mb-4">Subscription Details</h3>
          <div className="space-y-2">
            <p>
              <span className="font-medium">Status:</span>{" "}
              <span className="capitalize">{subscription.status}</span>
            </p>
            {subscription.currentPeriodEnd && (
              <p>
                <span className="font-medium">Next billing date:</span>{" "}
                {new Date(subscription.currentPeriodEnd).toLocaleDateString()}
              </p>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}

function CheckIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function LoaderIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="12" x2="12" y1="2" y2="6" />
      <line x1="12" x2="12" y1="18" y2="22" />
      <line x1="4.93" x2="7.76" y1="4.93" y2="7.76" />
      <line x1="16.24" x2="19.07" y1="16.24" y2="19.07" />
      <line x1="2" x2="6" y1="12" y2="12" />
      <line x1="18" x2="22" y1="12" y2="12" />
      <line x1="4.93" x2="7.76" y1="19.07" y2="16.24" />
      <line x1="16.24" x2="19.07" y1="7.76" y2="4.93" />
    </svg>
  );
}
