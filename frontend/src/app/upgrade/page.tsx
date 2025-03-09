"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Check, X } from "lucide-react";

export default function UpgradePage() {
  return (
    <div className="max-w-5xl mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-4">Upgrade Your Account</h1>
      <p className="text-muted-foreground mb-8">
        Get unlimited access to price history and advanced features
      </p>

      <div className="grid md:grid-cols-2 gap-8">
        <Card className="p-6">
          <div className="mb-8">
            <h2 className="text-2xl font-semibold mb-2">Free</h2>
            <p className="text-muted-foreground">
              Basic access for registered users
            </p>
          </div>

          <ul className="space-y-4 mb-8">
            <li className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-500" />
              <span>10 price history views per day</span>
            </li>
            <li className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-500" />
              <span>Basic search and filters</span>
            </li>
            <li className="flex items-center gap-2">
              <X className="h-5 w-5 text-red-500" />
              <span className="text-muted-foreground">
                Advanced price comparisons
              </span>
            </li>
            <li className="flex items-center gap-2">
              <X className="h-5 w-5 text-red-500" />
              <span className="text-muted-foreground">Price trend alerts</span>
            </li>
          </ul>

          <p className="text-2xl font-bold mb-6">$0 / month</p>
          <Button variant="outline" className="w-full" disabled>
            Current Plan
          </Button>
        </Card>

        <Card className="p-6 bg-primary/5 border-primary">
          <div className="mb-8">
            <h2 className="text-2xl font-semibold mb-2">Premium</h2>
            <p className="text-muted-foreground">
              Unlimited access to all features
            </p>
          </div>

          <ul className="space-y-4 mb-8">
            <li className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-500" />
              <span>Unlimited price history views</span>
            </li>
            <li className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-500" />
              <span>Advanced price comparisons</span>
            </li>
            <li className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-500" />
              <span>Price trend alerts</span>
            </li>
            <li className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-500" />
              <span>Data export capabilities</span>
            </li>
          </ul>

          <p className="text-2xl font-bold mb-6">$9.99 / month</p>
          <Button className="w-full" size="lg">
            Upgrade Now
          </Button>
        </Card>
      </div>
    </div>
  );
}
