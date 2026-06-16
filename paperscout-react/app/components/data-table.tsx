"use client";
import * as React from "react";
import { Input } from "~/components/ui/input";

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
import { Field } from "./ui/field";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  rowSelection?: any;
  onRowSelectionChange?: any;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  rowSelection,
  onRowSelectionChange,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    [],
  );

  const table = useReactTable({
    data,
    columns,
    getRowId: (row: any) => row.id, // Verknüpft Auswahl mit der ID statt Index
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    onRowSelectionChange: onRowSelectionChange,
    state: {
      sorting,
      columnFilters,
      rowSelection,
    },
    onColumnFiltersChange: setColumnFilters,
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <div className="flex flex-col h-full min-h-0">
      <Field className="py-4 shrink-0">
        <Input
          placeholder="Filter journals"
          value={(table.getColumn("name")?.getFilterValue() as string) ?? ""}
          onChange={(event) =>
            table.getColumn("name")?.setFilterValue(event.target.value)
          }
          className="max-w-sm"
        />
      </Field>
      
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
      <div className="grid grid-cols-1 md:grid-cols-3 rounded-md border shadow-sm flex-1 overflow-y-auto min-h-0 content-start">
        {table.getRowModel().rows?.length ? (
          table.getRowModel().rows.map((row) => (
            <div
              key={row.id} 
              data-state={row.getIsSelected() && "selected"} 
              className="flex items-start border-b p-2 transition-colors hover:bg-muted/50 has-aria-expanded:bg-muted/50 data-[state=selected]:bg-muted"
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
    </div>
  );
}
