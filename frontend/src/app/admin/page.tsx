"use client";

import { Card } from "@/components/ui/card";
import { Grid } from "@/components/ui/layout/Grid";
import { Metric } from "@/components/ui/metric/Metric";
import { BarChart } from "@/components/ui/charts/barChart";
import { Text } from "@/components/ui/text/Text";
import { Title } from "@/components/ui/text/Title";
import { useAnalysisStatus } from "@/lib/api/admin/analysis";
import { useActiveFieldMapping } from "@/lib/api/admin/field-harmonization";

export default function AdminDashboard() {
  const {
    data: statusSummary,
    isLoading: isLoadingStatus,
    isError: isErrorStatus,
    error: errorStatus,
  } = useAnalysisStatus();

  const {
    data: activeMappings,
    isLoading: isLoadingMappings,
    isError: isErrorMappings,
    error: errorMappings,
  } = useActiveFieldMapping();

  const isLoading = isLoadingStatus || isLoadingMappings;
  const overallError = errorStatus || errorMappings;
  let errorMessage: string | null = null;
  if (isErrorStatus) {
    errorMessage = `Failed to load analysis status: ${errorStatus?.message}`;
  }
  if (isErrorMappings) {
    const mappingErrorMsg = `Failed to load field mappings: ${errorMappings?.message}`;
    errorMessage = errorMessage
      ? `${errorMessage}; ${mappingErrorMsg}`
      : mappingErrorMsg;
  }

  const activeMappingsCount = activeMappings?.length;

  const chartData = [
    { date: "2023-01-01", "Active Users": 100, "New Listings": 20 },
    { date: "2023-02-01", "Active Users": 120, "New Listings": 25 },
    { date: "2023-03-01", "Active Users": 150, "New Listings": 30 },
    { date: "2023-04-01", "Active Users": 140, "New Listings": 28 },
    { date: "2023-05-01", "Active Users": 180, "New Listings": 35 },
    { date: "2023-06-01", "Active Users": 220, "New Listings": 42 },
  ];

  return (
    <div>
      <Title className="mb-4">Admin Overview</Title>
      <Text className="mb-6">
        View and manage system settings, analytics, and advanced features.
      </Text>

      {errorMessage && (
        <Text className="mb-4 text-red-600">Error: {errorMessage}</Text>
      )}

      <Grid numItems={1} numItemsSm={2} numItemsLg={3} className="mb-6 gap-6">
        <Card className="p-4">
          <Text>Total Listings</Text>
          <Metric>{isLoading ? "..." : (statusSummary?.total ?? "N/A")}</Metric>
        </Card>
        <Card className="p-4">
          <Text>Analyzed Listings</Text>
          <Metric>
            {isLoading ? "..." : (statusSummary?.completed ?? "N/A")}
          </Metric>
        </Card>
        <Card className="p-4">
          <Text>Active Field Mappings</Text>
          <Metric>{isLoading ? "..." : (activeMappingsCount ?? "N/A")}</Metric>
        </Card>
      </Grid>

      <Card className="mb-6 p-4">
        <Title>System Activity</Title>
        <BarChart
          data={chartData}
          index="date"
          categories={["Active Users", "New Listings"]}
          colors={["blue", "emerald"]}
          valueFormatter={(value) => `${value}`}
          yAxisWidth={40}
          className="mt-4 h-72"
          type="default"
        />
      </Card>

      <Text className="text-center text-gray-500">
        Select a tab above to manage specific administrative features.
      </Text>
    </div>
  );
}
