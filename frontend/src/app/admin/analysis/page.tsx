import AnalysisControls from "@/app/admin/analysis/AnalysisControls";
import { Card } from "@/components/ui/card";
import AnalysisStatus from "@/app/admin/analysis/AnalysisStatus";
import { Title } from "@/components/ui/text/Title";

export default function AnalysisPage() {
  return (
    <div className="space-y-6">
      <Title>Analysis Dashboard</Title>

      <div className="mx-auto max-w-7xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-bold">Analysis</h1>
        </div>

        <div className="mb-8">
          <Card className="p-6">
            <AnalysisStatus />
          </Card>
        </div>

        <AnalysisControls />
      </div>
    </div>
  );
}
