import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";

import { EmptyState } from "./States";

const isNil = (value) => value === null || value === undefined;

function compare(a, b) {
  if (a === b) return 0;
  return typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), "ru");
}

/**
 * Таблица. Если передан `onSort`, сортировка и пагинация выполняются на сервере (controlled),
 * иначе таблица сортирует переданные строки локально.
 */
export default function DataTable({
  columns, rows, rowKey, sort, onSort, page, onPage, onRowClick, selectedKey, emptyHint, caption,
}) {
  const [localSort, setLocalSort] = useState({ by: null, dir: "asc" });
  const active = onSort ? sort : localSort;

  const sorted = useMemo(() => {
    if (onSort || !localSort.by) return rows;
    const column = columns.find((item) => item.key === localSort.by);
    const read = column?.sortValue ?? ((row) => row[localSort.by]);
    const factor = localSort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = read(a);
      const right = read(b);
      // Пустые значения всегда в конце, независимо от направления сортировки.
      if (isNil(left) || isNil(right)) return Number(isNil(left)) - Number(isNil(right));
      return factor * compare(left, right);
    });
  }, [rows, columns, localSort, onSort]);

  const toggle = (key) => {
    const dir = active?.by === key && active.dir === "asc" ? "desc" : "asc";
    if (onSort) onSort({ by: key, dir });
    else setLocalSort({ by: key, dir });
  };

  if (!rows.length) return <EmptyState hint={emptyHint} />;

  const from = page ? page.offset + 1 : 0;
  const to = page ? Math.min(page.offset + page.limit, page.total) : 0;

  return (
    <div className="dash-table-wrap">
      <div className="dash-table-scroll">
        <table className="dash-table">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={column.align === "right" ? "right" : ""}
                  aria-sort={active?.by === column.key ? (active.dir === "asc" ? "ascending" : "descending") : undefined}>
                  {column.sortable ? (
                    <button type="button" className="th-sort" onClick={() => toggle(column.key)}>
                      {column.header}
                      {active?.by === column.key && (active.dir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                    </button>
                  ) : column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const key = rowKey(row);
              return (
                <tr key={key} className={`${onRowClick ? "clickable" : ""} ${selectedKey === key ? "selected" : ""}`}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}>
                  {columns.map((column) => (
                    <td key={column.key} className={column.align === "right" ? "right" : ""}>
                      {column.render ? column.render(row) : (row[column.key] ?? "—")}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {page && (
        <div className="dash-pagination">
          <span>{from}–{to} из {page.total}</span>
          <button type="button" className="dash-button ghost" aria-label="Предыдущая страница"
            disabled={page.offset === 0} onClick={() => onPage(Math.max(page.offset - page.limit, 0))}>
            <ChevronLeft size={14} />
          </button>
          <button type="button" className="dash-button ghost" aria-label="Следующая страница"
            disabled={page.offset + page.limit >= page.total} onClick={() => onPage(page.offset + page.limit)}>
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
