"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SubscriptionSuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");

  useEffect(() => {
    if (!sessionId) {
      router.push("/subscription");
    }
  }, [sessionId, router]);

  return (
    <div className="container max-w-4xl mx-auto py-8 px-4">
      <Card className="p-8 text-center">
        <div className="mb-6">
          <SuccessIcon className="mx-auto h-12 w-12 text-green-500" />
        </div>
        <h1 className="text-2xl font-bold mb-4">Subscription Successful!</h1>
        <p className="text-gray-600 mb-6">
          Thank you for subscribing. You now have full access to all premium
          features.
        </p>
        <Button onClick={() => router.push("/")}>Return to Dashboard</Button>
      </Card>
    </div>
  );
}

function SuccessIcon(props: React.SVGProps<SVGSVGElement>) {
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
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
