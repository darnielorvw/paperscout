import { describe, expect, it } from "vitest";
import {
  formatDateForApi,
  formatDateForDisplay,
  normalizeDateRange,
  normalizeToStartOfDay,
} from "./date-utils";

describe("normalizeToStartOfDay", () => {
  it("returns null for empty input", () => {
    expect(normalizeToStartOfDay(undefined)).toBeNull();
    expect(normalizeToStartOfDay(null)).toBeNull();
    expect(normalizeToStartOfDay("")).toBeNull();
  });

  it("returns null for an unparseable string", () => {
    expect(normalizeToStartOfDay("not-a-date")).toBeNull();
  });

  it("strips the time component", () => {
    const result = normalizeToStartOfDay(new Date("2024-03-07T15:42:10"));
    expect(result?.getHours()).toBe(0);
    expect(result?.getMinutes()).toBe(0);
    expect(result?.getSeconds()).toBe(0);
  });

  it("accepts a date string", () => {
    const result = normalizeToStartOfDay("2024-03-07T09:00:00");
    expect(result).toBeInstanceOf(Date);
    expect(result?.getFullYear()).toBe(2024);
    expect(result?.getMonth()).toBe(2);
    expect(result?.getDate()).toBe(7);
  });
});

describe("normalizeDateRange", () => {
  it("returns undefined when the range is undefined", () => {
    expect(normalizeDateRange(undefined)).toBeUndefined();
  });

  it("normalizes both ends of the range", () => {
    const result = normalizeDateRange({
      from: new Date("2024-03-07T12:00:00"),
      to: new Date("2024-03-20T23:59:59"),
    });
    expect(result?.from?.getHours()).toBe(0);
    expect(result?.to?.getHours()).toBe(0);
  });

  it("turns an invalid end date into undefined", () => {
    const result = normalizeDateRange({
      from: new Date("2024-03-07"),
      to: new Date("invalid"),
    });
    expect(result?.from).toBeInstanceOf(Date);
    expect(result?.to).toBeUndefined();
  });
});

describe("formatDateForApi", () => {
  it("formats a valid date as yyyy-MM-dd", () => {
    expect(formatDateForApi(new Date(2024, 2, 7, 10))).toBe("2024-03-07");
  });

  it("returns undefined for undefined or invalid input", () => {
    expect(formatDateForApi(undefined)).toBeUndefined();
    expect(formatDateForApi(null)).toBeUndefined();
    expect(formatDateForApi(new Date("invalid"))).toBeUndefined();
  });
});

describe("formatDateForDisplay", () => {
  it("formats as 'MMM yyyy'", () => {
    expect(formatDateForDisplay(new Date(2024, 2, 7))).toBe("Mar 2024");
  });

  it("accepts a string", () => {
    expect(formatDateForDisplay("2024-12-15T09:00:00")).toBe("Dec 2024");
  });

  it("returns an empty string for missing or invalid input", () => {
    expect(formatDateForDisplay(undefined)).toBe("");
    expect(formatDateForDisplay(null)).toBe("");
    expect(formatDateForDisplay("nope")).toBe("");
  });
});
