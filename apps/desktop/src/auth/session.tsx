import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ApiError, setAuthHooks } from "../api/client";
import { logoutServer } from "../api/v1";
import {
  AuthError,
  buildAuthUrl,
  config,
  discover,
  exchangeCode,
  makePkce,
  parseCallback,
  refreshTokens,
  revoke,
  type Meta,
  type Tokens,
} from "./oidc";
import { native as realNative, type Native } from "./native";

export type SessionState = "loading" | "signed-out" | "signing-in" | "signed-in";
interface Ctx {
  state: SessionState;
  notice: string | null; // why we are signed out (expired, cancelled, error); null otherwise
  signIn(): Promise<void>;
  signOut(): Promise<void>;
  cancel(): void; // abandons a pending sign-in
}
const SessionCtx = createContext<Ctx | null>(null);
export const useSession = () => useContext(SessionCtx)!;

const EXPIRED = "Your session expired. Please sign in again.";
const msg = (e: unknown) =>
  e instanceof AuthError || e instanceof ApiError ? e.message : "Something went wrong signing in.";

export function SessionProvider({ children, native = realNative }: { children: ReactNode; native?: Native }) {
  const [state, setState] = useState<SessionState>("loading");
  const [notice, setNotice] = useState<string | null>(null);
  const tokens = useRef<Tokens | null>(null); // access token: memory only
  const meta = useRef<Meta | null>(null);
  const inflight = useRef<Promise<boolean> | null>(null);
  const attempt = useRef(0); // lets a newer sign-in/out supersede a pending one (cancellation)

  const getMeta = async () => (meta.current ??= await discover(config().issuer));

  const lost = useCallback(
    async (why: string | null) => {
      tokens.current = null;
      await native.clearRefresh().catch(() => {});
      setNotice(why);
      setState("signed-out");
    },
    [native],
  );

  // Single-flight so concurrent 401s share one refresh (refresh tokens may rotate).
  const refresh = useCallback(() => {
    inflight.current ??= (async () => {
      try {
        const rt = tokens.current?.refresh ?? (await native.loadRefresh());
        if (!rt) return false;
        const t = await refreshTokens(await getMeta(), rt);
        tokens.current = t;
        if (t.refresh) await native.saveRefresh(t.refresh);
        return true;
      } catch (e) {
        if (e instanceof AuthError && e.kind !== "network") return false;
        throw new ApiError("network", "Cannot reach the sign-in service. Check your connection and retry.");
      } finally {
        inflight.current = null;
      }
    })();
    return inflight.current;
  }, [native]);

  const getToken = useCallback(async () => {
    const t = tokens.current;
    if (t && t.expiresAt - 30_000 > Date.now()) return t.access;
    if (!(await refresh())) return null;
    return tokens.current?.access ?? null;
  }, [refresh]);

  useEffect(() => {
    setAuthHooks({
      getToken,
      refresh: () => refresh().catch(() => false),
      onSessionLost: () => void lost(EXPIRED),
    });
    return () => setAuthHooks(null);
  }, [getToken, refresh, lost]);

  // Restore on launch: a stored refresh token yields a session; an explicit rejection means expired.
  useEffect(() => {
    let live = true;
    (async () => {
      const has = await native.loadRefresh().catch(() => null);
      if (!has) return live && setState("signed-out");
      try {
        const ok = await refresh();
        if (!live) return;
        if (ok) setState("signed-in");
        else await lost(EXPIRED);
      } catch {
        // IdP unreachable: keep the stored token, let the user retry.
        if (live) {
          setNotice("Cannot reach the sign-in service. Check your connection and retry.");
          setState("signed-out");
        }
      }
    })();
    return () => {
      live = false;
    };
  }, [native, refresh, lost]);

  const signIn = useCallback(async () => {
    const me = ++attempt.current;
    setNotice(null);
    setState("signing-in");
    try {
      const m = await getMeta();
      const pkce = await makePkce();
      const port = await native.listen();
      const redirect = `http://127.0.0.1:${port}/callback`;
      await native.openBrowser(buildAuthUrl(m, redirect, pkce));
      const code = parseCallback(await native.waitCallback(), pkce.state);
      const t = await exchangeCode(m, code, pkce.verifier, redirect);
      if (me !== attempt.current) return;
      if (t.refresh) await native.saveRefresh(t.refresh);
      tokens.current = t;
      setState("signed-in");
    } catch (e) {
      if (me !== attempt.current) return;
      setNotice(e instanceof AuthError && e.kind === "cancelled" ? "Sign-in cancelled." : msg(e));
      setState("signed-out");
    }
  }, [native]);

  const signOut = useCallback(async () => {
    attempt.current++;
    const t = tokens.current;
    // Best effort and in order: revoke server-side sessions while we still hold a token, then local state.
    await logoutServer().catch(() => {});
    if (t?.refresh && meta.current) await revoke(meta.current, t.refresh);
    await lost(null);
  }, [lost]);

  const cancel = useCallback(() => {
    attempt.current++;
    setNotice("Sign-in cancelled.");
    setState("signed-out");
  }, []);

  const value = useMemo(
    () => ({ state, notice, signIn, signOut, cancel }),
    [state, notice, signIn, signOut, cancel],
  );
  return <SessionCtx.Provider value={value}>{children}</SessionCtx.Provider>;
}
