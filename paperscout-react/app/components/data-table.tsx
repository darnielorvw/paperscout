"use client";
import type { OnChangeFn } from "@tanstack/react-table";
import * as React from "react";

import {
  type ColumnDef,
  type ColumnFiltersState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { SkeletonTable } from "./skeletons";
import { Field } from "./ui/field";
import { Input } from "./ui/input";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  isLoading?: boolean;
  rowSelection?: any;
  onRowSelectionChange?: any;
}

interface DataTableInnerProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  rowSelection?: any;
  onRowSelectionChange?: any;
  columnFilters: ColumnFiltersState;
  onColumnFiltersChange: OnChangeFn<ColumnFiltersState>;
}

function DataTableInner<TData, TValue>({
  columns,
  data,
  rowSelection,
  onRowSelectionChange,
  columnFilters,
  onColumnFiltersChange,
}: DataTableInnerProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    getRowId: (row: any) => row.id,
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    onRowSelectionChange,
    state: { sorting, columnFilters, rowSelection },
    onColumnFiltersChange: onColumnFiltersChange,
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <>
      {/* Header */}
      <div className="ml-auto w-full flex items-center gap-4 mb-4 rounded-md border bg-muted/30 px-3 py-1.5 shadow-sm shrink-0">
        {table.getHeaderGroups().map((headerGroup) => (
          <React.Fragment key={headerGroup.id}>
            {headerGroup.headers.map((header) => (
              <div key={header.id} className="flex items-center">
                {header.isPlaceholder
                  ? null
                  : flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
              </div>
            ))}
          </React.Fragment>
        ))}
      </div>

      {/* Rows */}
      <div className="grid grid-cols-1 md:grid-cols-3 rounded-md border shadow-sm flex-1 overflow-y-auto min-h-0 content-start">
        {table.getRowModel().rows?.length ? (
          table.getRowModel().rows.map((row) => (
            <div
              key={row.id}
              data-state={row.getIsSelected() && "selected"}
              className="flex items-start border-b p-2 transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted"
            >
              {row.getVisibleCells().map((cell) => (
                <div
                  key={cell.id}
                  className={`text-left align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-4 ${
                    cell.column.id === "select"
                      ? "flex-shrink-0"
                      : "flex-1 overflow-hidden"
                  }`}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </div>
              ))}
            </div>
          ))
        ) : (
          <div className="col-span-full flex h-12 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
            No results.
          </div>
        )}
      </div>
    </>
  );
}

export function DataTable<TData, TValue>({
  columns,
  data,
  isLoading = false,
  rowSelection,
  onRowSelectionChange,
}: DataTableProps<TData, TValue>) {
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    [],
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <Field className="py-4 shrink-0">
        <Input
          placeholder="Filter journals"
          value={
            (columnFilters.find((f) => f.id === "name")?.value as string) ?? ""
          }
          onChange={(e) =>
            setColumnFilters([{ id: "name", value: e.target.value }])
          }
          className="max-w-sm"
        />
      </Field>

      {isLoading ? (
        <SkeletonTable />
      ) : (
        <DataTableInner
          columns={columns}
          data={data}
          rowSelection={rowSelection}
          onRowSelectionChange={onRowSelectionChange}
          columnFilters={columnFilters}
          onColumnFiltersChange={setColumnFilters}
        />
      )}
    </div>
  );
}
