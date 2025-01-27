import AnalysisControls from "@/components/AnalysisControls";
import { Card } from "@/components/ui/card";
import AnalysisStatus from "@/components/AnalysisStatus";

export default function AnalysisPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Analysis</h1>
      </div>

      <div className="mb-8">
        <Card className="p-6">
          <AnalysisStatus />
        </Card>
      </div>

      <AnalysisControls />
    </div>
  );
}
