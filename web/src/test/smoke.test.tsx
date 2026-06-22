import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Markdown } from "../components/Markdown";
import { LoginPage } from "../pages/Login";

describe("Markdown", () => {
  it("renders GFM content", () => {
    render(<Markdown content={"# Title\n\n- **bold** item"} />);
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("bold")).toBeInTheDocument();
  });
});

describe("LoginPage", () => {
  it("renders the welcome screen", () => {
    render(<LoginPage onLoggedIn={() => {}} configured />);
    expect(screen.getByText("Welcome to Dax")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
  });
});
