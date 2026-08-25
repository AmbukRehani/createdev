import { useMutation } from "@tanstack/react-query";
import { postQuery } from "./client";
import type { QueryRequest, QueryResponse } from "./types";

// POST /api/v1/query is a user-triggered write, not a cacheable read, so
// this uses TanStack Query's useMutation rather than useQuery.
export function useSubmitQuery() {
  return useMutation<QueryResponse, Error, QueryRequest>({
    mutationFn: postQuery,
  });
}
