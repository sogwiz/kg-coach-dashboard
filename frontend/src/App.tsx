import { useEffect, useState } from "react";

type HealthStatus = "checking" | "connected" | "error";

export default function App() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    fetch("/health")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { status: string }) => {
        if (data.status === "ok") {
          setStatus("connected");
        } else {
          setStatus("error");
        }
      })
      .catch(() => setStatus("error"));
  }, []);

  const statusConfig = {
    checking: {
      bg: "bg-yellow-50",
      border: "border-yellow-200",
      dot: "bg-yellow-400",
      label: "Checking connection...",
      text: "text-yellow-800",
    },
    connected: {
      bg: "bg-green-50",
      border: "border-green-200",
      dot: "bg-green-500",
      label: "Connected",
      text: "text-green-800",
    },
    error: {
      bg: "bg-red-50",
      border: "border-red-200",
      dot: "bg-red-500",
      label: "Backend unreachable",
      text: "text-red-800",
    },
  }[status];

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full mx-auto p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          KG Coach Dashboard
        </h1>
        <p className="text-gray-500 text-sm mb-8">
          Knowledge-Graph-Backed Workout Planner
        </p>

        <div
          className={`rounded-lg border p-4 flex items-center gap-3 ${statusConfig.bg} ${statusConfig.border}`}
        >
          <span
            className={`w-3 h-3 rounded-full flex-shrink-0 ${statusConfig.dot}`}
          />
          <span className={`text-sm font-medium ${statusConfig.text}`}>
            Backend API: {statusConfig.label}
          </span>
        </div>

        <p className="mt-6 text-xs text-gray-400 text-center">
          Phase 1 scaffold — full dashboard coming in later phases
        </p>
      </div>
    </div>
  );
}
