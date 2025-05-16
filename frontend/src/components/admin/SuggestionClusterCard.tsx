'use client';

import React from 'react';
import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from '@/components/ui/layout/table';
import { Card } from '@/components/ui/card';
import { Title } from '@/components/ui/text/Title';
import { Text } from '@/components/ui/text/Text';
import { Badge } from '@/components/ui/badge';
import type { FieldCluster } from '@/app/admin/field-harmonization/page'; // Adjust path if necessary

interface SuggestionClusterCardProps {
  cluster: FieldCluster;
}

const getBadgeColor = (type: string | undefined): string => {
  switch (type) {
    case 'numeric': return 'blue';
    case 'categorical': return 'green';
    case 'boolean': return 'amber';
    case 'text': return 'indigo';
    default: return 'gray';
  }
};

export default function SuggestionClusterCard({ cluster }: SuggestionClusterCardProps) {
  return (
    <Card key={cluster.id}>
      <Title>{cluster.canonical_field}</Title>
      {cluster.suggested_name && (
        <Badge color="purple" className="ml-2">Suggested: {cluster.suggested_name}</Badge>
      )}
      
      <div className="mt-2">
        <Text><strong>Similar Fields:</strong></Text>
        <div className="flex flex-wrap gap-2 mt-1">
          {cluster.similar_fields.map((field) => (
            <Badge key={field} color="blue">
              {field} ({(cluster.similarity_scores[field] * 100).toFixed(0)}%)
            </Badge>
          ))}
        </div>
      </div>
      
      <Table className="mt-4">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Field</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>Example Values</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell>{cluster.canonical_field}</TableCell>
            <TableCell>
              <Badge color={getBadgeColor(cluster.field_types[cluster.canonical_field])}>
                {cluster.field_types[cluster.canonical_field] || 'unknown'}
              </Badge>
            </TableCell>
            <TableCell>
              {cluster.patterns[cluster.canonical_field]?.value_examples.slice(0, 3).map((ex: string, idx: number) => (
                <Badge key={idx} color="gray" className="mr-1">{ex}</Badge>
              ))}
            </TableCell>
          </TableRow>
          {cluster.similar_fields.map((field) => (
            <TableRow key={field}>
              <TableCell>{field}</TableCell>
              <TableCell>
                <Badge color={getBadgeColor(cluster.field_types[field])}>
                  {cluster.field_types[field] || 'unknown'}
                </Badge>
              </TableCell>
              <TableCell>
                {cluster.patterns[field]?.value_examples.slice(0, 3).map((ex: string, idx: number) => (
                  <Badge key={idx} color="gray" className="mr-1">{ex}</Badge>
                ))}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
} 