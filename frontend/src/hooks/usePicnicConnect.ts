import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { listrApi } from "../api/listrClient";

/** Connects to Picnic (login, then 2FA if Picnic asks for it) -- shared by every place that
 * needs a live session before doing something Picnic-specific (pushing a list to the cart,
 * importing a recipe). See docs/adr/0011-listr-picnic-integration.md.
 *
 * Callers render their own trigger button/wording and call `connect()` from it; `onConnected`
 * fires once a usable session actually exists, whether that took a 2FA round trip or not, so
 * the caller can chain straight into whatever it actually wanted to do. */
export function usePicnicConnect(onConnected: () => void) {
  const queryClient = useQueryClient();
  const [awaiting2FA, setAwaiting2FA] = useState(false);
  const [code, setCode] = useState("");

  const statusQuery = useQuery({
    queryKey: ["listr-picnic-status"],
    queryFn: () => listrApi.picnicStatus(),
  });

  const invalidateStatus = () => queryClient.invalidateQueries({ queryKey: ["listr-picnic-status"] });

  const loginMutation = useMutation({
    mutationFn: () => listrApi.picnicLogin(),
    onSuccess: (result) => {
      if (result.requires_2fa) {
        setAwaiting2FA(true);
      } else {
        invalidateStatus();
        onConnected();
      }
    },
  });

  const verifyMutation = useMutation({
    mutationFn: () => listrApi.picnicVerify2FA(code),
    onSuccess: () => {
      setAwaiting2FA(false);
      setCode("");
      invalidateStatus();
      onConnected();
    },
  });

  function connect() {
    if (statusQuery.data?.connected) {
      onConnected();
    } else {
      loginMutation.mutate();
    }
  }

  function cancel() {
    setAwaiting2FA(false);
    setCode("");
  }

  return {
    status: statusQuery.data,
    connect,
    isConnecting: loginMutation.isPending,
    connectError: loginMutation.isError,
    awaiting2FA,
    code,
    setCode,
    verify: () => verifyMutation.mutate(),
    isVerifying: verifyMutation.isPending,
    verifyError: verifyMutation.isError,
    cancel,
  };
}
