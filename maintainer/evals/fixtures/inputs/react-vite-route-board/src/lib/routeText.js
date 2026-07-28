const STATUS_LABELS = {
  ready: "Ready",
  attention: "Needs attention",
  delayed: "Delayed",
};

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? "Unknown";
}

export function matchesStop(stop, query) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  if (!normalizedQuery) {
    return true;
  }

  return [stop.name, stop.zone, stop.id]
    .join(" ")
    .toLocaleLowerCase()
    .includes(normalizedQuery);
}
