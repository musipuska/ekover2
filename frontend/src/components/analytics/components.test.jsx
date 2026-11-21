import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ChartCard from "./ChartCard";
import DataTable from "./DataTable";
import KpiCard from "./KpiCard";
import StatusBadge from "./StatusBadge";

describe("KpiCard", () => {
  it("shows N/A for a missing value and no unit", () => {
    render(<KpiCard label="Аномалии" value={null} unit="шт." description="d" />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.queryByText("шт.")).not.toBeInTheDocument();
  });

  it("shows a real zero", () => {
    render(<KpiCard label="Ошибки" value={0} unit="шт." />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows the delta only when the backend sent one", () => {
    const { rerender } = render(<KpiCard label="x" value={5} />);
    expect(screen.queryByText(/предыдущему периоду/)).not.toBeInTheDocument();
    rerender(<KpiCard label="x" value={5} delta={{ previous: 4, change: 1, change_pct: 25 }} />);
    expect(screen.getByText(/\+1 \(\+25%\)/)).toBeInTheDocument();
    rerender(<KpiCard label="x" value={5} delta={{ previous: 0, change: 5, change_pct: null }} />);
    expect(screen.getByText("+5 к предыдущему периоду")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("keeps backend status values and shows unknown ones as they are", () => {
    render(<><StatusBadge value="passed" /><StatusBadge value="success" /><StatusBadge value="legacy_status" /></>);
    expect(screen.getByText("PASSED")).toHaveAttribute("data-status", "passed");
    expect(screen.getByText("legacy_status")).toHaveClass("badge-muted");
  });
});

describe("ChartCard", () => {
  it("renders loading, error with retry, empty and content states", async () => {
    const reload = vi.fn();
    const { rerender } = render(<ChartCard title="t" state={{ loading: true }}><p>content</p></ChartCard>);
    expect(screen.getByRole("status")).toBeInTheDocument();

    rerender(<ChartCard title="t" state={{ loading: false, error: new Error("boom"), reload }}><p>content</p></ChartCard>);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
    await userEvent.click(screen.getByRole("button", { name: /Повторить/ }));
    expect(reload).toHaveBeenCalledOnce();

    rerender(<ChartCard title="t" state={{ loading: false }} isEmpty emptyHint="нет данных за период"><p>content</p></ChartCard>);
    expect(screen.getByText("нет данных за период")).toBeInTheDocument();
    expect(screen.queryByText("content")).not.toBeInTheDocument();

    rerender(<ChartCard title="t" state={{ loading: false }}><p>content</p></ChartCard>);
    expect(screen.getByText("content")).toBeInTheDocument();
  });
});

describe("DataTable", () => {
  const rows = [{ id: 1, name: "b", n: 2 }, { id: 2, name: "a", n: null }, { id: 3, name: "c", n: 10 }];
  const columns = [
    { key: "name", header: "Имя", sortable: true },
    { key: "n", header: "Число", sortable: true, align: "right" },
  ];
  const firstColumn = () => within(screen.getByRole("table")).getAllByRole("row").slice(1).map((r) => r.cells[0].textContent);

  it("sorts locally, with nulls always last", async () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    await userEvent.click(screen.getByRole("button", { name: "Число" }));
    expect(firstColumn()).toEqual(["b", "c", "a"]);
    await userEvent.click(screen.getByRole("button", { name: "Число" }));
    expect(firstColumn()).toEqual(["c", "b", "a"]);
  });

  it("delegates sorting and paging to the server when handlers are given", async () => {
    const onSort = vi.fn();
    const onPage = vi.fn();
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} sort={{ by: "name", dir: "asc" }} onSort={onSort}
      page={{ limit: 3, offset: 3, total: 9 }} onPage={onPage} />);
    expect(screen.getByText("4–6 из 9")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Имя" }));
    expect(onSort).toHaveBeenCalledWith({ by: "name", dir: "desc" });
    await userEvent.click(screen.getByRole("button", { name: "Следующая страница" }));
    expect(onPage).toHaveBeenCalledWith(6);
    await userEvent.click(screen.getByRole("button", { name: "Предыдущая страница" }));
    expect(onPage).toHaveBeenCalledWith(0);
  });

  it("disables paging at the edges and calls onRowClick", async () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} page={{ limit: 10, offset: 0, total: 3 }} onPage={() => {}} onRowClick={onRowClick} />);
    expect(screen.getByRole("button", { name: "Предыдущая страница" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Следующая страница" })).toBeDisabled();
    await userEvent.click(screen.getByText("a"));
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
  });

  it("shows an empty state instead of an empty table", () => {
    render(<DataTable columns={columns} rows={[]} rowKey={(r) => r.id} emptyHint="пусто" />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("пусто")).toBeInTheDocument();
  });
});
