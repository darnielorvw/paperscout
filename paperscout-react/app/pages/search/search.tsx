"use client";

import type { KeyboardEvent } from "react";
import { Field } from "~/components/ui/field";
import { Input } from "~/components/ui/input";

interface SearchPageProps {
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  onSearch: () => void;
}

export default function SearchPage({ searchTerm, onSearchTermChange, onSearch }: SearchPageProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      onSearch();
    }
  };
  return (
    <div className="flex h-full w-full flex-col items-center justify-center md:p-1">
      <Field className="w-full max-w-2xl">
        <Input 
          placeholder="Search Term" 
          className="pl-8 h-12 w-full rounded-full text-2xl" 
          value={searchTerm}
          onChange={(e) => onSearchTermChange(e.target.value)}
          onKeyDown={handleKeyDown}
        />
      </Field>
    </div>
  );
}
