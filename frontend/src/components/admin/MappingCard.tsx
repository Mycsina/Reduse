"use client";

import React from "react";
import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from "@/components/ui/layout/table";
import { Title } from "@/components/ui/text/Title";
import { Text } from "@/components/ui/text/Text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type {
  FieldHarmonizationMapping,
  FieldMapping,
} from "@/lib/api/admin/field-harmonization";

interface MappingCardProps {
  mapping: FieldHarmonizationMapping;
  onApply: (mappingId: string) => void;
  onEdit: (mappingId: string) => void;
  onDelete: (mappingId: string) => void;
  onUpdate: (updates: Partial<FieldHarmonizationMapping>) => void;
  isSubmitting?: boolean;
}

export default function MappingCard({
  mapping,
  onApply,
  onEdit,
  onDelete,
  onUpdate,
  isSubmitting = false,
}: MappingCardProps) {
  return (
    <Card
      className={`${mapping.is_active ? "border-2 border-green-500" : ""} p-4`}
    >
      <div className="flex items-start justify-between">
        <div className="px-2 py-1">
          <Title>{mapping.name}</Title>
          <div className="mt-1 flex gap-2">
            <Badge color={mapping.is_active ? "green" : "gray"}>
              {mapping.is_active ? "Active" : "Inactive"}
            </Badge>
            <Badge color="gray">
              {new Date(mapping.created_at).toLocaleDateString()}
            </Badge>
          </div>
          {mapping.description && (
            <Text className="mt-2">{mapping.description}</Text>
          )}
        </div>
        <div className="flex gap-2">
          {!mapping.is_active && (
            <Button onClick={() => onApply(mapping._id)} disabled={isSubmitting}>
              Apply
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => onEdit(mapping._id)}
            disabled={isSubmitting}
          >
            Edit
          </Button>
          <Button
            variant="destructive"
            onClick={() => onDelete(mapping._id)}
            disabled={isSubmitting}
          >
            Delete
          </Button>
        </div>
      </div>

      <div className="mt-6 px-2">
        <Title className="mb-3 text-sm">Rules ({mapping.mappings.length})</Title>
        <div className="max-h-60 overflow-y-auto">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Original Field</TableHeaderCell>
                <TableHeaderCell>Target Field</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mapping.mappings.map((rule: FieldMapping, idx: number) => (
                <TableRow key={`${mapping._id}-rule-${idx}`}>
                  <TableCell>{rule.original_field}</TableCell>
                  <TableCell>{rule.target_field}</TableCell>
                </TableRow>
              ))}
              {mapping.mappings.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="text-muted-foreground text-center"
                  >
                    No rules defined
                  </TableCell>
                </TableRow>
              )}
              {mapping.mappings.length > 10 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center">
                    <Text className="text-muted-foreground text-sm">
                      + {mapping.mappings.length - 10} more rules
                    </Text>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </Card>
  );
}
