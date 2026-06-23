export function StatusBadge({ status }) {
  const map = {
    idle: "pmos-badge-idle",
    running: "pmos-badge-running",
    success: "pmos-badge-success",
    error: "pmos-badge-error",
    warning: "pmos-badge-warning",
    open: "pmos-badge-magenta",
    closed: "pmos-badge-idle",
  };
  return (
    <span className={`pmos-badge ${map[status] || "pmos-badge-idle"}`} data-testid={`status-badge-${status}`}>
      {status || "idle"}
    </span>
  );
}
