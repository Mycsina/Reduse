"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { toast } from "@/hooks/use-toast";
import { Title } from "@/components/ui/text/Title";
import LoadingSpinner from "@/components/ui/loading-spinner";

import {
  useScrapeUrlMutation,
} from "@/lib/api/admin/scrape";

export default function ScrapePage() {
  const [url, setUrl] = useState("");
  const [progress, setProgress] = useState<{
    phase: string;
    current: number;
    total: number;
  } | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const scrapeUrlMutation = useScrapeUrlMutation();

  const isLoading = scrapeUrlMutation.isPending;

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const setupEventSource = (queueId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    const eventSourceUrl = new URL(
      `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/scrape/logs/${queueId}`,
    );
    const apiKey = localStorage.getItem("api_key");
    if (apiKey) {
      eventSourceUrl.searchParams.append("api_key", apiKey);
    } else {
      console.warn("API key not found for EventSource. SSE might fail.");
    }

    const source = new EventSource(eventSourceUrl.toString());
    eventSourceRef.current = source;

    source.onopen = () => {
      setProgress(null);
    };

    source.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "progress") {
        setProgress(data);
      } else if (
        data.type === "completed" ||
        data.message?.includes("Processing complete") ||
        data.message?.includes("No listings found to process")
      ) {
        toast({
          title: "Success",
          description: data.message || "Operation completed",
        });
        source.close();
        setProgress(null);
      } else if (data.type === "error") {
        toast({
          title: "Scraping Error",
          description: data.message,
          variant: "destructive",
        });
        source.close();
        setProgress(null);
      } else if (data.type === "log") {
        console.log("SSE Log:", data.message);
      }
    };

    source.onerror = (err) => {
      console.error("EventSource failed:", err);
      toast({
        title: "Connection Lost",
        description: "Lost connection to server for progress updates.",
        variant: "destructive",
      });
      source.close();
      setProgress(null);
    };
  };

  const handleScrape = async (type: "url" | "olx") => {
    setProgress(null);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      let response;
      if (type === "url") {
        if (!url) {
          toast({
            title: "Input Error",
            description: "Please enter a URL.",
            variant: "destructive",
          });
          return;
        }
        response = await scrapeUrlMutation.mutateAsync(url);
      }

      if (response && response.queue_id) {
        setupEventSource(response.queue_id);
      } else {
        toast({
          title: "Error",
          description: "Failed to get queue ID for scraping.",
          variant: "destructive",
        });
      }
    } catch (error) {
      setProgress(null);
      console.error("Scrape initiation error:", error);
    }
  };

  return (
    <div className="space-y-6">
      <Title>Scraping Configuration</Title>
      <div className="grid gap-8">
        <Card className="p-6">
          <h2 className="mb-4 text-xl font-semibold">URL Scraping</h2>
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
              disabled={isLoading || !url || scrapeUrlMutation.isPending}
            >
              {scrapeUrlMutation.isPending ? (
                <LoadingSpinner className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {scrapeUrlMutation.isPending ? "Processing..." : "Scrape URL"}
            </Button>
          </div>
        </Card>

        {(isLoading || progress) && (
          <Card className="p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Progress</h2>
                {progress && (
                  <span className="text-muted-foreground text-sm">
                    {progress.phase}: {progress.current} / {progress.total}
                  </span>
                )}
                {isLoading && !progress && (
                  <span className="text-muted-foreground text-sm">
                    Initiating...
                  </span>
                )}
              </div>
              {progress && progress.total > 0 && (
                <Progress
                  value={(progress.current / progress.total) * 100}
                  className="h-3"
                />
              )}
              {isLoading && !progress && (
                <Progress value={undefined} className="h-3 animate-pulse" />
              )}{" "}
              {/* Indeterminate progress */}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
