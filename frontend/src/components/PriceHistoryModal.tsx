"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiClient } from "@/lib/api-client";
import { formatPrice } from "@/lib/utils";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

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
  const [priceHistory, setPriceHistory] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isOpen && baseModel) {
      setIsLoading(true);
      apiClient
        .getModelPriceHistory(baseModel, 30)
        .then((data) => {
          setPriceHistory(data);
        })
        .catch((error) => {
          console.error("Failed to fetch price history:", error);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [isOpen, baseModel]);

  const chartData = {
    labels: priceHistory.map((item) =>
      new Date(item.timestamp).toLocaleDateString()
    ),
    datasets: [
      {
        label: "Median Price",
        data: priceHistory.map((item) => item.median_price),
        borderColor: "rgb(75, 192, 192)",
        tension: 0.1,
      },
      {
        label: "Average Price",
        data: priceHistory.map((item) => item.avg_price),
        borderColor: "rgb(255, 99, 132)",
        tension: 0.1,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: "top" as const,
      },
      title: {
        display: true,
        text: `Price History for ${brand} ${baseModel}`,
      },
    },
    scales: {
      y: {
        ticks: {
          callback: (value: number) => formatPrice(value),
        },
      },
    },
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[800px]">
        <DialogHeader>
          <DialogTitle>Price History</DialogTitle>
        </DialogHeader>
        <div className="h-[400px]">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              Loading...
            </div>
          ) : priceHistory.length > 0 ? (
            <Line data={chartData} options={options} />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              No price history available
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
