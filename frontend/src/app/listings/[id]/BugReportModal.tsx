"use client";

import { useState, useMemo } from "react";
import { Listing } from "@/lib/api/query/query";
import { AnalyzedListing } from "@/lib/api/admin/analysis";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../../../components/ui/dialog";
import { Button } from "../../../components/ui/button";
import { Textarea } from "../../../components/ui/textarea";
import { Label } from "../../../components/ui/label";
import { RadioGroup, RadioGroupItem } from "../../../components/ui/radio-group";
import { Input } from "../../../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../components/ui/select";
import { Check, AlertCircle } from "lucide-react";
import {
  useCreateBugReportMutation,
  BugReportCreate,
} from "@/lib/api/bug-reports";
import { toast } from "@/hooks/use-toast";

// Helper function to format field names
const formatFieldName = (field: string): string => {
  const parts = field.split(".");
  return parts[parts.length - 1];
};

// Bug report types correspond to backend enum
export enum BugReportType {
  INCORRECT_DATA = "incorrect_data",
  MISSING_DATA = "missing_data",
  WRONG_ANALYSIS = "wrong_analysis",
  OTHER = "other",
}

interface BugReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  listing: Listing;
  analysis?: AnalyzedListing | null;
}

// Define fields to exclude from the dropdown
const excludedListingFields = [
  "_id",
  "photo_urls",
  "parameters",
  "more",
  "analysis_status",
  "analysis_error",
  "retry_count",
];
const excludedAnalysisFields = [
  "_id",
  "parsed_listing_id",
  "original_listing_id",
  "info",
  "embeddings",
  "analysis_version",
  "retry_count",
];

export default function BugReportModal({
  isOpen,
  onClose,
  listing,
  analysis,
}: BugReportModalProps) {
  const [reportType, setReportType] = useState<BugReportType>(
    BugReportType.INCORRECT_DATA,
  );
  const [description, setDescription] = useState("");
  const [incorrectFields, setIncorrectFields] = useState<Record<string, any>>(
    {},
  );
  const [expectedValues, setExpectedValues] = useState<Record<string, any>>({});
  const [isSuccessDisplay, setIsSuccessDisplay] = useState(false);
  const [selectedField, setSelectedField] = useState<string>("");
  const [fieldValue, setFieldValue] = useState("");

  const { mutateAsync: submitBugReport, isPending } =
    useCreateBugReportMutation();

  // Dynamically generate allowed fields based on listing and analysis props
  const allowedFields = useMemo(() => {
    const fields: string[] = [];

    // Add listing fields
    for (const key in listing) {
      if (!excludedListingFields.includes(key) && !key.startsWith("_")) {
        fields.push(key);
      }
    }

    // Add analysis top-level fields
    if (analysis) {
      for (const key in analysis) {
        if (!excludedAnalysisFields.includes(key) && !key.startsWith("_")) {
          fields.push(`analysis.${key}`);
        }
      }

      // Add analysis info fields
      if (analysis.info && typeof analysis.info === "object") {
        for (const key in analysis.info) {
          fields.push(`analysis.info.${key}`);
        }
      }
    }

    return [...new Set(fields)].sort(); // Ensure unique and sort
  }, [listing, analysis]);

  // Reset form state when modal opens/closes
  const handleClose = () => {
    if (!isPending) {
      setReportType(BugReportType.INCORRECT_DATA);
      setDescription("");
      setIncorrectFields({});
      setExpectedValues({});
      setIsSuccessDisplay(false);
      setSelectedField("");
      setFieldValue("");
      onClose();
    }
  };

  // Get the current value of a potentially nested field
  const getCurrentFieldValue = (field: string): string => {
    if (!field) return "N/A";
    try {
      let value: any;
      if (field.startsWith("analysis.info.")) {
        const infoKey = field.substring("analysis.info.".length);
        value = analysis?.info?.[infoKey];
      } else if (field.startsWith("analysis.")) {
        const analysisKey = field.substring("analysis.".length);
        value = analysis?.[analysisKey as keyof AnalyzedListing];
      } else {
        value = listing[field as keyof Listing];
      }

      // Handle different value types appropriately
      if (value === null || value === undefined) return "N/A";
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
    } catch (error) {
      console.error(`Error getting field value for ${field}:`, error);
      return "Error";
    }
  };

  // Add a field to the incorrect fields list using the selected field
  const addField = () => {
    if (selectedField && fieldValue.trim()) {
      const currentVal = getCurrentFieldValue(selectedField);

      setIncorrectFields((prev) => ({
        ...prev,
        [selectedField]: currentVal,
      }));

      setExpectedValues((prev) => ({
        ...prev,
        [selectedField]: fieldValue,
      }));

      setSelectedField("");
      setFieldValue("");
    }
  };

  // Remove a field from the incorrect fields list
  const removeField = (field: string) => {
    const newIncorrectFields = { ...incorrectFields };
    const newExpectedValues = { ...expectedValues };

    delete newIncorrectFields[field];
    delete newExpectedValues[field];

    setIncorrectFields(newIncorrectFields);
    setExpectedValues(newExpectedValues);
  };

  // Handle form submission
  const handleSubmit = async () => {
    if (!description) {
      toast({
        title: "Missing description",
        description: "Please provide a description of the issue.",
        variant: "destructive",
      });
      return;
    }

    const payload: BugReportCreate = {
      listing_id: listing._id || "",
      original_id: listing.original_id,
      site: listing.site,
      report_type: reportType,
      description,
      incorrect_fields:
        Object.keys(incorrectFields).length > 0 ? incorrectFields : null,
      expected_values:
        Object.keys(expectedValues).length > 0 ? expectedValues : null,
    };

    try {
      await submitBugReport(payload);

      setIsSuccessDisplay(true);
      toast({
        title: "Bug report submitted",
        description:
          "Thank you for your feedback. Your report will help improve our data quality.",
      });

      // Auto-close after success
      setTimeout(() => {
        handleClose();
      }, 2000);
    } catch (error) {
      console.error("Error submitting bug report (component):", error);
      toast({
        title: "Error submitting report",
        description:
          "There was a problem submitting your report. Please try again.",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Report Issue with Listing</DialogTitle>
        </DialogHeader>

        {isSuccessDisplay ? (
          <div className="flex flex-col items-center justify-center py-8">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
              <Check className="h-6 w-6 text-green-600" />
            </div>
            <h3 className="text-lg font-medium">
              Thank you for your feedback!
            </h3>
            <p className="text-muted-foreground mt-2 text-center">
              Your report will help us improve our data quality.
            </p>
          </div>
        ) : (
          <>
            <div className="grid gap-4 py-4">
              <div className="mb-2">
                <Label>What type of issue are you reporting?</Label>
                <RadioGroup
                  value={reportType}
                  onValueChange={(value) =>
                    setReportType(value as BugReportType)
                  }
                  className="mt-2 space-y-2"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem
                      value={BugReportType.INCORRECT_DATA}
                      id="incorrect_data"
                    />
                    <Label htmlFor="incorrect_data">
                      Incorrect data (price, title, etc.)
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem
                      value={BugReportType.MISSING_DATA}
                      id="missing_data"
                    />
                    <Label htmlFor="missing_data">Missing data</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem
                      value={BugReportType.WRONG_ANALYSIS}
                      id="wrong_analysis"
                    />
                    <Label htmlFor="wrong_analysis">
                      Incorrect analysis/categorization
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value={BugReportType.OTHER} id="other" />
                    <Label htmlFor="other">Other issue</Label>
                  </div>
                </RadioGroup>
              </div>

              <div className="mb-2">
                <Label htmlFor="description" className="mb-2 block">
                  Describe the issue
                </Label>
                <Textarea
                  id="description"
                  placeholder="Please provide details about the issue..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={5}
                  className="w-full"
                />
              </div>

              {reportType === BugReportType.INCORRECT_DATA && (
                <div className="bg-muted/20 mb-2 rounded-md border p-4">
                  <Label className="mb-2 block">Specify incorrect fields</Label>

                  <div className="mb-3 flex items-center gap-2">
                    <div className="flex-1">
                      <Select
                        value={selectedField}
                        onValueChange={setSelectedField}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select field..." />
                        </SelectTrigger>
                        <SelectContent>
                          {allowedFields.map((field) => (
                            <SelectItem key={field} value={field}>
                              {formatFieldName(field)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {selectedField && (
                        <p className="text-muted-foreground mt-1 text-sm">
                          Current value: {getCurrentFieldValue(selectedField)}
                        </p>
                      )}
                    </div>
                    <div className="flex-1">
                      <Input
                        placeholder="Expected value"
                        value={fieldValue}
                        onChange={(e) => setFieldValue(e.target.value)}
                      />
                    </div>
                    <Button
                      variant="outline"
                      onClick={addField}
                      disabled={!selectedField || !fieldValue.trim()}
                    >
                      Add
                    </Button>
                  </div>

                  {Object.keys(incorrectFields).length > 0 ? (
                    <div className="mt-4 space-y-2">
                      <Label className="text-sm font-medium">
                        Fields to correct:
                      </Label>
                      {Object.keys(incorrectFields).map((field) => (
                        <div
                          key={field}
                          className="bg-background flex items-center justify-between rounded-md p-2 text-sm"
                        >
                          <div>
                            <span className="font-medium">
                              {formatFieldName(field)}
                            </span>
                            : Change from &quot;
                            <span className="text-destructive">
                              {String(incorrectFields[field])}
                            </span>
                            &quot; to &quot;
                            <span className="text-green-600">
                              {expectedValues[field]}
                            </span>
                            &quot;
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeField(field)}
                            className="h-6 w-6 p-0"
                          >
                            ×
                          </Button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-muted-foreground mt-2 flex items-center text-sm">
                      <AlertCircle className="mr-2 h-4 w-4" />
                      No incorrect fields specified yet
                    </div>
                  )}
                </div>
              )}
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={handleClose}
                disabled={isPending}
              >
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={isPending}>
                {isPending ? "Submitting..." : "Submit Report"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
