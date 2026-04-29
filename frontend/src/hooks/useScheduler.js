import { useQuery } from "@tanstack/react-query";
import { getSchedulerStatus } from "../lib/api";

export function useScheduler() {
  const schedulerQuery = useQuery({
    queryKey: ["scheduler"],
    queryFn: getSchedulerStatus,
    refetchInterval: 30_000,
  });

  return {
    scheduler: schedulerQuery.data,
    isLoading: schedulerQuery.isLoading,
    error: schedulerQuery.error,
  };
}
