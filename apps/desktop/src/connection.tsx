import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getHealth } from "./api/client";

export type Connection = "checking" | "online" | "offline";
const Ctx = createContext<{ status: Connection; recheck: () => void }>({
  status: "checking",
  recheck: () => {},
});
export const useConnection = () => useContext(Ctx);

export function ConnectionProvider({
  children,
  intervalMs = 15_000,
}: {
  children: ReactNode;
  intervalMs?: number;
}) {
  const [status, setStatus] = useState<Connection>("checking");
  const recheck = useCallback(() => {
    getHealth().then(
      () => setStatus("online"),
      () => setStatus("offline"),
    );
  }, []);
  useEffect(() => {
    recheck();
    const t = setInterval(recheck, intervalMs);
    return () => clearInterval(t);
  }, [recheck, intervalMs]);
  return <Ctx.Provider value={{ status, recheck }}>{children}</Ctx.Provider>;
}
