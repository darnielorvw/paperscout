// app/routes/_index.tsx
import { useEffect, useMemo } from "react";
import { useLoaderData, useLocation, useNavigate } from "react-router";
import { InputAccordion } from "~/components/input-accordion";
import { useSearch } from "~/context/search-context";
import { apiFetch } from "~/lib/api";
import { protectPage } from "~/lib/auth";
import { buildResultsUrl } from "~/lib/search-utils";
import { type Journal } from "~/pages/journals/columns";
import JournalsPage from "~/pages/journals/journals";
import RangePage from "~/pages/range/range";
import SearchPage from "~/pages/search/search";

export function clientLoader(): { journals: Promise<Journal[]> } {
  // Protect this page: if there's no token, execution stops here and redirects.
  protectPage();

  const journals = apiFetch("/api/journals")
    .then((data) => {
      return (data.results as Journal[]) || [];
    });

  return { journals };
}

export default function Home() {
  // Selection state for the journals
  const { journals } = useLoaderData<typeof clientLoader>();
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
        initialData={journals}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
      />
    ),
    [journals, rowSelection, setRowSelection],
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
