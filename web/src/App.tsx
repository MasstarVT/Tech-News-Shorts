import {X} from "lucide-react";
import React, {createContext, useContext, useEffect, useRef, useState} from "react";
import {api, type Meta, type Task, type Tasks} from "./api";
import {ByteMark, Clock, Tally} from "./components/ui";
import {go, useLoad, useRoute} from "./lib";
import {AutoPage} from "./pages/Auto";
import {JobPage} from "./pages/Job";
import {JobsPage} from "./pages/Jobs";
import {SettingsPage} from "./pages/Settings";
import {TodayPage} from "./pages/Today";

type Room = {
  meta: Meta | null;
  tasks: Tasks | null;
  /** Bumps whenever a task finishes, so pages refetch what it changed. */
  version: number;
  refreshTasks: () => void;
  held: number;
  setHeld: (n: number) => void;
};

const RoomCtx = createContext<Room>({meta: null, tasks: null, version: 0, refreshTasks: () => {}, held: 0, setHeld: () => {}});
export const useRoom = () => useContext(RoomCtx);

const NAV = [
  {href: "#/", label: "Today", match: (r: string) => r === "/"},
  {href: "#/jobs", label: "Jobs", match: (r: string) => r.startsWith("/jobs")},
  {href: "#/auto", label: "Auto", match: (r: string) => r === "/auto"},
  {href: "#/settings", label: "Settings", match: (r: string) => r === "/settings"},
];

const Login: React.FC<{onDone: () => void}> = ({onDone}) => {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  return (
    <main className="login">
      <div className="brand">
        <ByteMark size={34} />
        Byte Brief control room
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api.login(token);
            onDone();
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
          }
        }}
      >
        <div className="field">
          <label className="label" htmlFor="token">
            Access token
          </label>
          <input id="token" type="password" autoComplete="current-password" value={token} onChange={(e) => setToken(e.target.value)} />
          <span className="help">The TECHNEWS_WEB_TOKEN value from the server's .env file.</span>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <button className="btn primary" type="submit" disabled={!token}>
          Sign in
        </button>
      </form>
    </main>
  );
};

export const App: React.FC = () => {
  const route = useRoute();
  const session = useLoad(api.session);
  const [signedOut, setSignedOut] = useState(false);
  const signedIn = session.data ? session.data.signed_in && !signedOut : false;

  useEffect(() => {
    const on = () => setSignedOut(true);
    window.addEventListener("tn:signed-out", on);
    return () => window.removeEventListener("tn:signed-out", on);
  }, []);

  if (session.error && !session.data) {
    return (
      <main className="login">
        <p className="error-text">Can't reach the server: {session.error}</p>
        <button className="btn" onClick={() => void session.reload()}>
          Try again
        </button>
      </main>
    );
  }
  if (!session.data) return null;
  if (!signedIn)
    return (
      <Login
        onDone={() => {
          setSignedOut(false);
          void session.reload();
        }}
      />
    );
  return <Room route={route} />;
};

const Room: React.FC<{route: string}> = ({route}) => {
  const meta = useLoad(api.meta);
  const [tasks, setTasks] = useState<Tasks | null>(null);
  const [version, setVersion] = useState(0);
  const [notices, setNotices] = useState<Task[]>([]);
  const [held, setHeld] = useState(0);
  const seen = useRef<Set<string> | null>(null);

  const poll = async () => {
    try {
      const t = await api.tasks();
      setTasks(t);
      const finished = t.recent.filter((x) => x.status === "done" || x.status === "failed");
      if (seen.current === null) {
        seen.current = new Set(finished.map((x) => x.id));
        return;
      }
      const fresh = finished.filter((x) => !seen.current!.has(x.id));
      if (fresh.length) {
        fresh.forEach((x) => seen.current!.add(x.id));
        setVersion((v) => v + 1);
        const failed = fresh.filter((x) => x.status === "failed");
        if (failed.length) setNotices((n) => [...failed, ...n].slice(0, 3));
      }
    } catch {
      /* the next poll retries */
    }
  };

  useEffect(() => {
    void poll();
    const t = window.setInterval(() => void poll(), 1500);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    api.jobs().then((jobs) => setHeld(jobs.filter((j) => j.held).length), () => {});
  }, [version]);

  const jobMatch = route.match(/^\/jobs\/(.+)$/);
  let page: React.ReactNode;
  if (route === "/") page = <TodayPage />;
  else if (jobMatch) page = <JobPage id={decodeURIComponent(jobMatch[1])} />;
  else if (route.startsWith("/jobs")) page = <JobsPage />;
  else if (route === "/auto") page = <AutoPage />;
  else if (route === "/settings") page = <SettingsPage />;
  else page = <TodayPage />;

  const room: Room = {meta: meta.data, tasks, version, refreshTasks: () => void poll(), held, setHeld};
  const live = Boolean(tasks?.current?.live);

  return (
    <RoomCtx.Provider value={room}>
      <header className="bar">
        <a className="brand" href="#/" onClick={() => go("/")}>
          <ByteMark live={live} />
          {meta.data?.brand ?? "Byte Brief"}
        </a>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => (
            <a key={n.href} href={n.href} aria-current={n.match(route) ? "page" : undefined}>
              {n.label}
              {n.label === "Jobs" && held ? (
                <span className="count" title={`${held} waiting for approval`}>
                  {held}
                </span>
              ) : null}
            </a>
          ))}
        </nav>
        <div className="bar-right">
          <Tally tasks={tasks} />
          <Clock />
        </div>
      </header>
      {notices.length ? (
        <div className="notices" role="alert">
          {notices.map((n) => (
            <div className="notice" key={n.id}>
              <span className="msg">
                <strong>{n.title.split(":")[0]} failed.</strong> {n.error}
              </span>
              {n.job_id ? (
                <a className="btn small" href={`#/jobs/${n.job_id}`}>
                  Open job
                </a>
              ) : null}
              <button className="btn quiet small" aria-label="Dismiss" onClick={() => setNotices((all) => all.filter((x) => x.id !== n.id))}>
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      ) : null}
      <main className="page">{page}</main>
    </RoomCtx.Provider>
  );
};
