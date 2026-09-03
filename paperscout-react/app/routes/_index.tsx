// app/routes/_index.tsx
import { useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router";
import { InputAccordion } from "~/components/input-accordion";
import { useJournals } from "~/context/journals-context";
import { useSearch } from "~/context/search-context";
import { protectPage } from "~/lib/auth";
import { buildResultsUrl } from "~/lib/search-utils";
import JournalsPage from "~/pages/journals/journals";
import RangePage from "~/pages/range/range";
import SearchPage from "~/pages/search/search";

export function clientLoader() {
  // The journal list lives in JournalsProvider (loaded once per session), so
  // this route only needs the auth gate.
  protectPage();
  return null;
}

export default function Home() {
  // Selection state for the journals
  const { journals, isLoading: journalsLoading } = useJournals();
  const {
    rowSelection,
    setRowSelection,
    date,
    setDate,
    searchTerm,
    setSearchTerm,
  } = useSearch();

  // State for the results
  const navigate = useNavigate(); // Hook for navigation
  const location = useLocation();

  // Effect to ensure the home page always points to #journals.
  useEffect(() => {
    if (location.pathname === "/" && !location.hash) {
      navigate("/#journals", { replace: true, preventScrollReset: true });
    }
  }, [location, navigate]);

  const handleSearch = async () => {
    const resultsUrl = buildResultsUrl({ rowSelection, date, searchTerm });
    navigate(resultsUrl);
  };

  // Memoize the accordion item contents to prevent unnecessary remounting
  const journalsContent = useMemo(
    () => (
      <JournalsPage
        data={journals}
        isLoading={journalsLoading}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
      />
    ),
    [journals, journalsLoading, rowSelection, setRowSelection],
  );

  const rangeContent = useMemo(
    () => <RangePage date={date} onDateChange={setDate} />,
    [date],
  );

  const searchContent = useMemo(
    () => (
      <SearchPage
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
        onSearch={handleSearch}
      />
    ),
    [searchTerm, setSearchTerm, handleSearch],
  );

  const accordionItems = useMemo(
    () => [
      {
        value: "journals",
        trigger: "Search for Journals",
        content: journalsContent,
      },
      {
        value: "range",
        trigger: "Enter a Search Time Range",
        content: rangeContent,
      },
      {
        value: "search",
        trigger: "Enter a Search Term",
        content: searchContent,
      },
    ],
    [journalsContent, rangeContent, searchContent],
  );

  return (
    <div className="h-full w-full">
      <InputAccordion
        title="PaperScout Dashboard"
        description="Choose an action from the menu."
        items={accordionItems}
        onFinish={handleSearch}
      />
    </div>
  );
}
