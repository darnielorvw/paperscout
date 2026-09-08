import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// React Testing Library doesn't auto-clean when `globals` is combined with a
// custom setup file, so do it explicitly between tests.
afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
});
