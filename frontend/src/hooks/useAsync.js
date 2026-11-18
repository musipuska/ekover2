import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Загрузка данных с отменой устаревших запросов.
 * `fetcher(signal)` должен вернуть `{ data, meta }`; `deps` — простые значения,
 * от которых зависит запрос. Результат старого запроса никогда не попадёт в state:
 * он сопоставляется по ключу запроса, а прерванный fetch игнорируется.
 */
export function useAsync(fetcher, deps, enabled = true) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ key: null, result: null, error: null, updatedAt: null });
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const requestKey = `${JSON.stringify(deps)}#${attempt}`;

  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();

    fetcherRef.current(controller.signal).then(
      (result) => {
        if (controller.signal.aborted) return;
        const stamp = result?.meta?.generated_at ?? new Date().toISOString();
        setState({ key: requestKey, result, error: null, updatedAt: stamp });
      },
      (error) => {
        if (controller.signal.aborted || error?.name === "AbortError") return;
        setState({ key: requestKey, result: null, error, updatedAt: null });
      },
    );

    return () => controller.abort();
  }, [requestKey, enabled]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  const current = state.key === requestKey;

  return {
    data: current ? (state.result?.data ?? null) : null,
    meta: current ? (state.result?.meta ?? null) : null,
    error: current ? state.error : null,
    loading: enabled && !current,
    updatedAt: current ? state.updatedAt : null,
    reload,
  };
}
