"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";

export default function ScrapePage() {
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<{
    phase: string;
    current: number;
    total: number;
  } | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Cleanup EventSource on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const setupEventSource = (queueId: string) => {
    const eventSourceUrl = new URL(
      `${
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
      }/scrape/logs/${queueId}`
    );
    eventSourceUrl.searchParams.append("api_key", apiClient.getApiKey());

    const source = new EventSource(eventSourceUrl.toString());
    eventSourceRef.current = source;

    source.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "progress") {
        setProgress(data);
      } else if (data.type === "error") {
        toast({
          title: "Error",
          description: data.message,
          variant: "destructive",
        });
        source.close();
        setIsLoading(false);
        setProgress(null);
      } else if (data.type === "log") {
        // Check for completion messages
        if (
          data.message.includes("Processing complete") ||
          data.message.includes("No listings found to process")
        ) {
          source.close();
          setIsLoading(false);
          setProgress(null);
          toast({
            title: "Success",
            description: "Operation completed",
          });
        }
      }
    };

    source.onerror = () => {
      source.close();
      setIsLoading(false);
      setProgress(null);
      toast({
        title: "Connection lost",
        description: "The connection to the server was lost",
        variant: "destructive",
      });
    };
  };

  const handleScrape = async (type: "url" | "olx") => {
    try {
      setIsLoading(true);
      setProgress(null);

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const response =
        type === "url"
          ? await apiClient.scrapeUrl(url)
          : await apiClient.scrapeOlxCategories();

      setupEventSource(response.queue_id);
    } catch (error) {
      setIsLoading(false);
      setProgress(null);
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "An error occurred",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Scraping</h1>
      </div>

      <div className="grid gap-8">
        {/* URL Scraping */}
        <Card className="p-6">
          <h2 className="text-xl font-semibold mb-4">URL Scraping</h2>
          <div className="flex gap-4">
            <Input
              type="url"
              placeholder="Enter URL to scrape"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              onClick={() => handleScrape("url")}
              disabled={isLoading || !url}
            >
              {isLoading ? "Processing..." : "Scrape URL"}
            </Button>
          </div>
        </Card>

        {/* OLX Category Scraping */}
        <Card className="p-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">OLX Category Scraping</h2>
            <Button onClick={() => handleScrape("olx")} disabled={isLoading}>
              {isLoading ? "Processing..." : "Scrape OLX Categories"}
            </Button>
          </div>
        </Card>

        {/* Progress Display */}
        {progress && (
          <Card className="p-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">Progress</h2>
                <span className="text-sm text-muted-foreground">
                  {progress.current} / {progress.total}
                </span>
              </div>
              <Progress
                value={(progress.current / progress.total) * 100}
                className="h-3"
              />
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
