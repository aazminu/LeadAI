import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createLead, getLeads } from "../lib/api";

export function useLeadPolling() {
  const queryClient = useQueryClient();
  const leadsQuery = useQuery({
    queryKey: ["leads"],
    queryFn: getLeads,
    refetchInterval: 10_000,
  });

  const createLeadMutation = useMutation({
    mutationFn: createLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  return {
    leads: leadsQuery.data || [],
    isLoading: leadsQuery.isLoading,
    error: leadsQuery.error,
    createLead: createLeadMutation.mutateAsync,
    isCreating: createLeadMutation.isPending,
  };
}
