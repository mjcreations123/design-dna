export function RouteSummary({ stops, reviewedCount }) {
  const readyCount = stops.filter((stop) => stop.status === "ready").length;
  const exceptionCount = stops.length - readyCount;

  return (
    <dl className="route-summary" aria-label="Route summary">
      <div>
        <dt>Stops</dt>
        <dd>{stops.length}</dd>
      </div>
      <div>
        <dt>Ready</dt>
        <dd>{readyCount}</dd>
      </div>
      <div>
        <dt>Exceptions</dt>
        <dd>{exceptionCount}</dd>
      </div>
      <div>
        <dt>Reviewed</dt>
        <dd>{reviewedCount}</dd>
      </div>
    </dl>
  );
}
