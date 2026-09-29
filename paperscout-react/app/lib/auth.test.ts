import { describe, expect, it } from "vitest";
import { protectPage } from "./auth";

describe("protectPage", () => {
  it("throws a redirect to /login when no token is present", () => {
    let thrown: unknown;
    try {
      protectPage();
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(Response);
    expect((thrown as Response).status).toBe(302);
    expect((thrown as Response).headers.get("Location")).toBe("/login");
  });

  it("does nothing when a token is stored", () => {
    localStorage.setItem("auth_token", "tok");
    expect(() => protectPage()).not.toThrow();
  });
});
