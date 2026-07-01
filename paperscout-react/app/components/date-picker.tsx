"use client";

import {
  endOfMonth,
  format,
  isSameMonth,
  startOfMonth,
  subMonths,
  subYears,
} from "date-fns";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import * as React from "react";
import { type DateRange } from "react-day-picker";

import { Button } from "~/components/ui/button";

interface DatePickerProps {
  date: DateRange | undefined;
  onDateChange: (date: DateRange | undefined) => void;
}

export function DatePicker({ date, onDateChange }: DatePickerProps) {
  const [startYear, setStartYear] = React.useState(new Date().getFullYear());
  const [endYear, setEndYear] = React.useState(new Date().getFullYear());

  const presets = [
    {
      label: "Current Month",
      getDates: () => {
        const now = new Date();
        return { from: startOfMonth(now), to: endOfMonth(now) };
      },
    },
    {
      label: "Last 3 Months",
      getDates: () => {
        const now = new Date();
        return { from: startOfMonth(subMonths(now, 2)), to: endOfMonth(now) };
      },
    },
    {
      label: "Last 12 Months",
      getDates: () => {
        const now = new Date();
        return { from: startOfMonth(subYears(now, 1)), to: endOfMonth(now) };
      },
    },
    {
      label: "Last 5 Years",
      getDates: () => {
        const now = new Date();
        return { from: startOfMonth(subYears(now, 5)), to: endOfMonth(now) };
      },
    },
    {
      label: "Last 10 Years",
      getDates: () => {
        const now = new Date();
        return { from: startOfMonth(subYears(now, 10)), to: endOfMonth(now) };
      },
    },
    {
      label: "Unlimited",
      getDates: () => {
        const now = new Date();
        return { from: startOfMonth(new Date(1900, 0)), to: endOfMonth(now) };
      },
    },
  ];

  const applyPreset = (getDates: () => { from: Date; to: Date }) => {
    const { from, to } = getDates();
    onDateChange({ from, to });
    setStartYear(from.getFullYear());
    setEndYear(to.getFullYear());
  };

  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  const handleStartMonthClick = (monthIndex: number) => {
    const newFrom = startOfMonth(new Date(startYear, monthIndex));
    if (date?.to && newFrom > date.to) {
      onDateChange({ from: newFrom, to: endOfMonth(newFrom) });
    } else {
      onDateChange({ from: newFrom, to: date?.to });
    }
  };

  const handleEndMonthClick = (monthIndex: number) => {
    const newTo = endOfMonth(new Date(endYear, monthIndex));
    if (date?.from && newTo < date.from) {
      onDateChange({ from: startOfMonth(newTo), to: newTo });
    } else {
      onDateChange({ from: date?.from, to: newTo });
    }
  };

  const isSelected = (year: number, monthIndex: number) => {
    const d = new Date(year, monthIndex);
    if (date?.from && isSameMonth(d, date.from)) return true;
    if (date?.to && isSameMonth(d, date.to)) return true;
    if (date?.from && date?.to && d >= date.from && d <= date.to) return true;
    return false;
  };

  return (
    <div className="flex w-full flex-col items-center gap-6 pb-4 pt-2">
      {/* Current Selection Display (Header) */}
      <div className="flex max-w-sm items-center justify-center gap-3 text-lg px-2 py-3 font-medium">
        <CalendarIcon className="h-5 w-5" />
        {date?.from && date?.to ? (
          isSameMonth(date.from, date.to) ? (
            format(date.from, "LLL y")
          ) : (
            <>
              {format(date.from, "LLL y")} - {format(date.to, "LLL y")}
            </>
          )
        ) : date?.from ? (
          format(date.from, "LLL y")
        ) : date?.to ? (
          format(date.to, "LLL y")
        ) : (
          <span>Pick a date</span>
        )}
      </div>

      {/* Main Calendar Container */}
      <div className="flex max-w-full flex-row gap-4 overflow-x-auto rounded-xl border bg-card p-4 shadow-sm">
        {/* Presets Sidebar */}
        <div className="flex w-40 shrink-0 flex-col gap-2">
          <div className="mb-2 text-center text-sm font-medium text-muted-foreground">
            Schnellauswahl
          </div>
          {presets.map((preset) => (
            <Button
              key={preset.label}
              variant="ghost"
              className="justify-start font-normal"
              onClick={() => applyPreset(preset.getDates)}
            >
              {preset.label}
            </Button>
          ))}
        </div>

        <div className="w-px bg-border my-2" />

        {/* Start Date Calendar */}
        <div className="w-64 shrink-0">
          <div className="mb-2 text-center text-sm font-medium text-muted-foreground">
            Start Date
          </div>
          <div className="flex items-center justify-between pb-4">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setStartYear(startYear - 1)}
            >
              <ChevronLeftIcon className="h-4 w-4" />
            </Button>
            <div className="font-semibold">{startYear}</div>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setStartYear(startYear + 1)}
            >
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {months.map((month, index) => {
              const selected = isSelected(startYear, index);
              return (
                <Button
                  key={`start-${month}`}
                  variant={selected ? "default" : "ghost"}
                  onClick={() => handleStartMonthClick(index)}
                  className="w-full"
                >
                  {month}
                </Button>
              );
            })}
          </div>
        </div>

        <div className="w-px bg-border my-2" />

        {/* End Date Calendar */}
        <div className="w-64 shrink-0">
          <div className="mb-2 text-center text-sm font-medium text-muted-foreground">
            End Date
          </div>
          <div className="flex items-center justify-between pb-4">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setEndYear(endYear - 1)}
            >
              <ChevronLeftIcon className="h-4 w-4" />
            </Button>
            <div className="font-semibold">{endYear}</div>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setEndYear(endYear + 1)}
            >
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {months.map((month, index) => {
              const selected = isSelected(endYear, index);
              return (
                <Button
                  key={`end-${month}`}
                  variant={selected ? "default" : "ghost"}
                  onClick={() => handleEndMonthClick(index)}
                  className="w-full"
                >
                  {month}
                </Button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
