// Tremor Table [v1.0.0]

import React from "react";

import { cx } from "@/lib/utils";

function TableRoot({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div data-slot="table-root-outer">
      <div
        data-slot="table-root-inner"
        className={cx("w-full overflow-auto whitespace-nowrap", className)}
        {...props}
      >
        {children}
      </div>
    </div>
  );
}

function Table({
  className,
  ...props
}: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table
      data-slot="table"
      className={cx(
        "w-full caption-bottom border-b",
        "border-gray-200 dark:border-gray-800",
        className,
      )}
      {...props}
    />
  );
}

function TableHead({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead data-slot="table-head" className={cx(className)} {...props} />;
}

function TableHeaderCell({
  className,
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      data-slot="table-header-cell"
      className={cx(
        "border-b px-4 py-3.5 text-left text-sm font-semibold",
        "text-gray-900 dark:text-gray-50",
        "border-gray-200 dark:border-gray-800",
        className,
      )}
      {...props}
    />
  );
}

function TableBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody
      data-slot="table-body"
      className={cx(
        "divide-y",
        "divide-gray-200 dark:divide-gray-800",
        className,
      )}
      {...props}
    />
  );
}

function TableRow({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      data-slot="table-row"
      className={cx(
        "[&_td:last-child]:pr-4 [&_th:last-child]:pr-4",
        "[&_td:first-child]:pl-4 [&_th:first-child]:pl-4",
        className,
      )}
      {...props}
    />
  );
}

function TableCell({
  className,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      data-slot="table-cell"
      className={cx(
        "p-4 text-sm",
        "text-gray-600 dark:text-gray-400",
        className,
      )}
      {...props}
    />
  );
}

function TableFoot({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tfoot
      data-slot="table-foot"
      className={cx(
        "border-t text-left font-medium",
        "text-gray-900 dark:text-gray-50",
        "border-gray-200 dark:border-gray-800",
        className,
      )}
      {...props}
    />
  );
}

function TableCaption({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableCaptionElement>) {
  return (
    <caption
      data-slot="table-caption"
      className={cx(
        "mt-3 px-3 text-center text-sm",
        "text-gray-500 dark:text-gray-500",
        className,
      )}
      {...props}
    />
  );
}

export {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFoot,
  TableHead,
  TableHeaderCell,
  TableRoot,
  TableRow,
};
