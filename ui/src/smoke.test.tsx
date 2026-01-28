import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Button } from "./components/ui/button";

describe("UI smoke test", () => {
  it("renders a basic component", () => {
    render(<Button>Ping</Button>);
    expect(screen.getByText("Ping")).toBeInTheDocument();
  });
});
