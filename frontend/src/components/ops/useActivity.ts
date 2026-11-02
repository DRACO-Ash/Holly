import { useCallback, useEffect, useState } from "react";
import { getActivity } from "../../api/activity";
import type { ActivityOverview } from "../../types";
import { extractErrorMessage } from "../../utils/errors";

export const ACTIVITY_REFRESH_MS = 60_000;

export interface ActivityState {
  data: ActivityOverview | null;
  error: string | null;
  loading: boolean;
  refreshing: boolean;
  loadedAt: number | null;
  reload: () => void;
}

// The activity overview, loaded once and then again every minute while the view is open. A
// failed reload keeps the last overview on screen and says why beside it.
export function useActivity(): ActivityState {
  const [data, setData] = useState<ActivityOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);
  const [token, setToken] = useState(0);

  const reload = useCallback(() => setToken((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setRefreshing(true);
    getActivity()
      .then((overview) => {
        if (cancelled) return;
        setData(overview);
        setError(null);
        setLoadedAt(Date.now());
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(extractErrorMessage(err, "Failed to load the activity overview."));
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
        setRefreshing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    const id = window.setInterval(reload, ACTIVITY_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [reload]);

  return { data, error, loading, refreshing, loadedAt, reload };
}
