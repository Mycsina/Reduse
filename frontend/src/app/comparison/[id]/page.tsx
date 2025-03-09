import { notFound } from "next/navigation";
import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import apiClient from "@/lib/api-client";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatPrice } from "@/lib/utils";
import { Listing, AnalysisStatus, AnalyzedListing } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Listing Comparison",
  description: "Compare listings side by side",
};

interface ComparisonData {
  field: string;
  current: string;
  similar: string;
}

function getComparisonData(
  currentListing: Listing,
  currentAnalysis: AnalyzedListing,
  similarListing: Listing,
  similarAnalysis: AnalyzedListing
): ComparisonData[] {
  const data: ComparisonData[] = [
    {
      field: "Price",
      current: formatPrice(currentListing.price_value ? parseFloat(currentListing.price_value) : 0),
      similar: formatPrice(similarListing.price_value ? parseFloat(similarListing.price_value) : 0),
    },
    {
      field: "Type",
      current: currentAnalysis.type || "-",
      similar: similarAnalysis.type || "-",
    },
    {
      field: "Brand",
      current: currentAnalysis.brand || "-",
      similar: similarAnalysis.brand || "-",
    },
    {
      field: "Base Model",
      current: currentAnalysis.base_model || "-",
      similar: similarAnalysis.base_model || "-",
    },
    {
      field: "Model Variant",
      current: currentAnalysis.model_variant || "-",
      similar: similarAnalysis.model_variant || "-",
    },
  ];

  // Add all info fields that exist in either listing
  const allInfoFields = new Set([
    ...Object.keys(currentAnalysis.info || {}),
    ...Object.keys(similarAnalysis.info || {}),
  ]);

  allInfoFields.forEach((field) => {
    data.push({
      field: field.replace(/_/g, " "),
      current: String(currentAnalysis.info?.[field] || "-"),
      similar: String(similarAnalysis.info?.[field] || "-"),
    });
  });

  return data;
}

export default async function ComparisonPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  try {
    // Fetch current listing and its analysis
    const currentListing = await apiClient.getListing(id);
    if (currentListing.analysis_status !== AnalysisStatus.COMPLETED) {
      notFound();
    }
    const currentAnalysis = await apiClient.getListingAnalysisByOriginalId(
      currentListing.original_id
    );

    // Fetch similar listing
    const similarListings = await apiClient.getSimilarListings(id);
    if (!similarListings.length) {
      notFound();
    }

    const similarListing = similarListings[0];
    const similarAnalysis = await apiClient.getListingAnalysisByOriginalId(
      similarListing.original_id
    );

    const comparisonData = getComparisonData(
      currentListing,
      currentAnalysis,
      similarListing,
      similarAnalysis
    );

    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold">Listing Comparison</h1>
          <Link href={`/listings/${id}`}>
            <Button variant="outline">Back to Listing</Button>
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
          {/* Current Listing Preview */}
          <Card className="p-4">
            <div className="relative aspect-video w-full mb-4">
              <Image
                src={currentListing.photo_url}
                alt={currentListing.title}
                fill
                className="object-cover rounded-lg"
              />
            </div>
            <h2 className="font-semibold">{currentListing.title}</h2>
          </Card>

          {/* Similar Listing Preview */}
          <Card className="p-4">
            <div className="relative aspect-video w-full mb-4">
              <Image
                src={similarListing.photo_url}
                alt={similarListing.title}
                fill
                className="object-cover rounded-lg"
              />
            </div>
            <h2 className="font-semibold">{similarListing.title}</h2>
          </Card>
        </div>

        {/* Comparison Table */}
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px]">Field</TableHead>
                <TableHead>Current Listing</TableHead>
                <TableHead>Similar Listing</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {comparisonData.map((row) => (
                <TableRow key={row.field}>
                  <TableCell className="font-medium capitalize">
                    {row.field}
                  </TableCell>
                  <TableCell>{row.current}</TableCell>
                  <TableCell>{row.similar}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    );
  } catch (error) {
    console.error("Error in comparison page:", error);
    notFound();
  }
}
