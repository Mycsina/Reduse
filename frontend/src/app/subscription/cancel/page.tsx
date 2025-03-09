"use client";

import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SubscriptionCancelPage() {
  const router = useRouter();

  return (
    <div className="container max-w-4xl mx-auto py-8 px-4">
      <Card className="p-8 text-center">
        <div className="mb-6">
          <InfoIcon className="mx-auto h-12 w-12 text-yellow-500" />
        </div>
        <h1 className="text-2xl font-bold mb-4">Subscription Cancelled</h1>
        <p className="text-gray-600 mb-6">
          Your subscription process was cancelled. You can try again whenever
          you&apos;re ready.
        </p>
        <div className="space-x-4">
          <Button
            onClick={() => router.push("/subscription")}
            variant="default"
          >
            Try Again
          </Button>
          <Button onClick={() => router.push("/")} variant="outline">
            Return to Dashboard
          </Button>
        </div>
      </Card>
    </div>
  );
}

function InfoIcon(props: React.SVGProps<SVGSVGElement>) {
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
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
