import { useMemo, useState } from "react";
import { RouteSummary } from "./components/RouteSummary.jsx";
import routeStops from "./data/route-stops.json";
import { matchesStop, statusLabel } from "./lib/routeText.js";

const STATUS_OPTIONS = [
  ["all", "All statuses"],
  ["ready", "Ready"],
  ["attention", "Needs attention"],
  ["delayed", "Delayed"],
];

export default function App() {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(routeStops[0]?.id ?? "");
  const [reviewedIds, setReviewedIds] = useState([]);
  const [notice, setNotice] = useState("No route updates recorded.");

  const visibleStops = useMemo(
    () =>
      routeStops.filter(
        (stop) =>
          matchesStop(stop, query) &&
          (statusFilter === "all" || stop.status === statusFilter),
      ),
    [query, statusFilter],
  );

  const selectedStop =
    visibleStops.find((stop) => stop.id === selectedId) ??
    visibleStops[0] ??
    null;

  function markReviewed() {
    if (!selectedStop || reviewedIds.includes(selectedStop.id)) {
      return;
    }

    setReviewedIds((current) => [...current, selectedStop.id]);
    setNotice(`${selectedStop.name} marked reviewed for this session.`);
  }

  function resetFilters() {
    setQuery("");
    setStatusFilter("all");
    setSelectedId(routeStops[0]?.id ?? "");
    setNotice("Filters cleared.");
  }

  return (
    <main className="app-shell">
      <header className="masthead">
        <div className="product-lockup">
          <img src="/assets/route-marker.svg" alt="" width="44" height="44" />
          <div>
            <p className="eyebrow">Fictional dispatch fixture</p>
            <h1>Meadowline route board</h1>
          </div>
        </div>
        <p className="day-label">Sample weekday run · local data only</p>
      </header>

      <RouteSummary stops={routeStops} reviewedCount={reviewedIds.length} />

      <section className="workspace" aria-label="Route review workspace">
        <div className="queue-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Dispatch queue</p>
              <h2>Review today&apos;s stops</h2>
            </div>
            <p className="result-count">
              {visibleStops.length} of {routeStops.length}
            </p>
          </div>

          <div className="filters">
            <label>
              Search stops
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Name, zone, or ID"
              />
            </label>
            <label>
              Status
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
              >
                {STATUS_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {visibleStops.length > 0 ? (
            <ol className="route-list">
              {visibleStops.map((stop) => {
                const isSelected = selectedStop?.id === stop.id;
                const isReviewed = reviewedIds.includes(stop.id);

                return (
                  <li key={stop.id}>
                    <button
                      className="route-row"
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => {
                        setSelectedId(stop.id);
                        setNotice(`${stop.name} selected.`);
                      }}
                    >
                      <span className="sequence">{stop.sequence}</span>
                      <span className="route-copy">
                        <strong>{stop.name}</strong>
                        <span>
                          {stop.zone} · {stop.arrival}
                        </span>
                      </span>
                      <span className={`status status-${stop.status}`}>
                        {statusLabel(stop.status)}
                      </span>
                      {isReviewed ? (
                        <span className="reviewed-label">Reviewed</span>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ol>
          ) : (
            <div className="empty-state">
              <h3>No routes match</h3>
              <p>Clear the current search and status filter to restore the queue.</p>
              <button type="button" onClick={resetFilters}>
                Clear filters
              </button>
            </div>
          )}
        </div>

        <aside className="detail-panel" aria-labelledby="detail-title">
          {selectedStop ? (
            <>
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Selected stop</p>
                  <h2 id="detail-title">{selectedStop.name}</h2>
                </div>
                <span className={`status status-${selectedStop.status}`}>
                  {statusLabel(selectedStop.status)}
                </span>
              </div>

              <dl className="stop-details">
                <div>
                  <dt>Route ID</dt>
                  <dd>{selectedStop.id}</dd>
                </div>
                <div>
                  <dt>Arrival</dt>
                  <dd>{selectedStop.arrival}</dd>
                </div>
                <div>
                  <dt>Load</dt>
                  <dd>{selectedStop.load}</dd>
                </div>
                <div>
                  <dt>Access</dt>
                  <dd>{selectedStop.access}</dd>
                </div>
              </dl>

              <p className="route-note">{selectedStop.note}</p>
              <button
                className="primary-action"
                type="button"
                onClick={markReviewed}
                disabled={reviewedIds.includes(selectedStop.id)}
              >
                {reviewedIds.includes(selectedStop.id)
                  ? "Reviewed"
                  : "Mark reviewed"}
              </button>
            </>
          ) : (
            <>
              <p className="eyebrow">Selected stop</p>
              <h2 id="detail-title">Nothing selected</h2>
              <p>Adjust or clear the filters to choose a route stop.</p>
            </>
          )}
        </aside>
      </section>

      <p className="session-notice" aria-live="polite">
        {notice}
      </p>
    </main>
  );
}
