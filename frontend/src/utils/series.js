const pad = (value) => String(value).padStart(2, "0");

/** Ключ временного интервала для даты YYYY-MM-DD: день, неделя (с понедельника) или месяц. */
export function bucketKey(day, grain) {
  if (grain === "month") return `${day.slice(0, 7)}-01`;
  if (grain === "week") {
    const [y, m, d] = day.split("-").map(Number);
    const date = new Date(Date.UTC(y, m - 1, d));
    const shift = (date.getUTCDay() + 6) % 7;
    date.setUTCDate(date.getUTCDate() - shift);
    return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
  }
  return day;
}

/**
 * Пересчёт дневных агрегатов витрины daily_metrics в более крупный интервал.
 * Среднее взвешивается числом измерений, min/max берутся по интервалу — результат точный.
 * Возвращает { [station]: [{ key, avg, min, max, count }] } отсортированный по времени;
 * ключ "__all__" — все станции вместе.
 */
export function aggregateTrends(rows, grain = "day") {
  const stations = new Map();
  const add = (station, key, row) => {
    if (!stations.has(station)) stations.set(station, new Map());
    const buckets = stations.get(station);
    const bucket = buckets.get(key) ?? { key, sum: 0, count: 0, min: Infinity, max: -Infinity };
    const count = row.measurement_count ?? 0;
    bucket.sum += (row.avg_value ?? 0) * count;
    bucket.count += count;
    bucket.min = Math.min(bucket.min, row.min_value ?? Infinity);
    bucket.max = Math.max(bucket.max, row.max_value ?? -Infinity);
    buckets.set(key, bucket);
  };

  rows.forEach((row) => {
    const key = bucketKey(row.date, grain);
    add("__all__", key, row);
    if (row.station_id !== null && row.station_id !== undefined) add(String(row.station_id), key, row);
  });

  const result = {};
  stations.forEach((buckets, station) => {
    result[station] = [...buckets.values()]
      .filter((bucket) => bucket.count > 0)
      .sort((a, b) => a.key.localeCompare(b.key))
      .map((bucket) => ({
        key: bucket.key,
        avg: bucket.sum / bucket.count,
        min: bucket.min,
        max: bucket.max,
        count: bucket.count,
      }));
  });
  return result;
}
