"use client";

import { type DateRange } from "react-day-picker";
import { DatePicker } from "~/components/date-picker";

interface RangePageProps {
  date: DateRange | undefined;
  onDateChange: (date: DateRange | undefined) => void;
}

export default function RangePage({ date, onDateChange }: RangePageProps) {
  return (
    <div className="flex h-full w-full flex-col md:p-1">
      <DatePicker date={date} onDateChange={onDateChange} />
    </div>
  );
}
