"use client";

import { useEffect, useState } from "react";
import { AreaChart } from "@/components/ui/charts/areaChart";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import apiClient from "@/lib/api-client";
import { formatPrice } from "@/lib/utils";

interface PriceHistoryEntry {
  _id: string;
  timestamp: string;
  median_price: number;
  avg_price: number;
}

interface PriceHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  baseModel: string;
  brand: string;
}

export default function PriceHistoryModal({
  isOpen,
  onClose,
  baseModel,
  brand,
}: PriceHistoryModalProps) {
  const [priceHistory, setPriceHistory] = useState<PriceHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isOpen && baseModel) {
      setIsLoading(true);
      apiClient
        .getModelPriceHistory(baseModel, 30)
        .then((data) => {
          const transformedData = data.map((item: any) => ({
            ...item,
            timestamp: new Date(item.timestamp || item._id).toLocaleDateString(
              "en-US",
              { month: "short", day: "numeric" },
            ),
            "Median Price": item.median_price,
            "Average Price": item.avg_price,
          }));
          setPriceHistory(transformedData);
        })
        .catch((error) => {
          console.error("Failed to fetch price history:", error);
          setPriceHistory([]);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else if (!isOpen) {
      setPriceHistory([]);
      setIsLoading(true);
    }
  }, [isOpen, baseModel]);

  const categories = ["Median Price", "Average Price"];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[800px]">
        <DialogHeader>
          <DialogTitle>Price History</DialogTitle>
        </DialogHeader>
        <div className="h-[400px]">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              Loading...
            </div>
          ) : priceHistory.length > 0 ? (
            <AreaChart
              className="h-full w-full"
              data={priceHistory}
              index="timestamp"
              categories={categories}
              colors={["cyan", "pink"]}
              valueFormatter={formatPrice}
              yAxisWidth={60}
              showLegend={true}
            />
          ) : (
            <div className="text-muted-foreground flex h-full items-center justify-center">
              No price history available
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
