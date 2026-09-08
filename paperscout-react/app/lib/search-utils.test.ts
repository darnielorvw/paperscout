import { describe, expect, it } from "vitest";
import { areFiltersEqual, buildResultsUrl } from "./search-utils";

describe("buildResultsUrl", () => {
  const date = { from: new Date(2024, 2, 1), to: new Date(2024, 2, 31) };

  it("adds only the selected journal ids", () => {
    const url = buildResultsUrl({
      rowSelection: { A: true, B: false, C: true },
      date,
      searchTerm: "",
    });
    const params = new URL(url, "http://x").searchParams;
    expect(params.getAll("journal_ids")).toEqual(["A", "C"]);
  });

  it("trims the search term into the keywords param", () => {
    const url = buildResultsUrl({
      rowSelection: {},
      date,
      searchTerm: "  machine learning  ",
    });
    expect(new URL(url, "http://x").searchParams.get("keywords")).toBe("machine learning");
  });

  it("includes from_date/to_date when a full range is given", () => {
    const url = buildResultsUrl({ rowSelection: {}, date, searchTerm: "" });
    const params = new URL(url, "http://x").searchParams;
    expect(params.get("from_date")).toBe("2024-03-01");
    expect(params.get("to_date")).toBe("2024-03-31");
  });

  it("omits the date params when the range is incomplete", () => {
    const url = buildResultsUrl({
      rowSelection: {},
      date: { from: new Date(2024, 2, 1), to: undefined },
      searchTerm: "",
    });
    const params = new URL(url, "http://x").searchParams;
    expect(params.has("from_date")).toBe(false);
    expect(params.has("to_date")).toBe(false);
  });

  it("omits the date params when date is undefined", () => {
    const url = buildResultsUrl({ rowSelection: {}, date: undefined, searchTerm: "x" });
    expect(new URL(url, "http://x").searchParams.has("from_date")).toBe(false);
  });

  it("targets the /results route", () => {
    const url = buildResultsUrl({ rowSelection: {}, date, searchTerm: "" });
    expect(url.startsWith("/results?")).toBe(true);
  });
});

describe("areFiltersEqual", () => {
  it("is true for identical selection and search term", () => {
    expect(
      areFiltersEqual(
        { rowSelection: { A: true, B: true }, searchTerm: "cats" },
        { rowSelection: { B: true, A: true }, searchTerm: "cats" },
      ),
    ).toBe(true);
  });

  it("ignores surrounding whitespace in the search term", () => {
    expect(
      areFiltersEqual(
        { rowSelection: {}, searchTerm: "cats" },
        { rowSelection: {}, searchTerm: "  cats  " },
      ),
    ).toBe(true);
  });

  it("is false when the journal selection differs", () => {
    expect(
      areFiltersEqual(
        { rowSelection: { A: true }, searchTerm: "x" },
        { rowSelection: { A: true, B: true }, searchTerm: "x" },
      ),
    ).toBe(false);
  });

  it("is false when the search term differs", () => {
    expect(
      areFiltersEqual(
        { rowSelection: {}, searchTerm: "cats" },
        { rowSelection: {}, searchTerm: "dogs" },
      ),
    ).toBe(false);
  });
});
