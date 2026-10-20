import React, {useState} from "react";
import {api, type JobSummary} from "../api";
import {useRoom} from "../App";
import {Checks, StageLights, stageStates, statusText} from "../components/ui";
import {go, shortDate, tcf, useLoad} from "../lib";

// A dry run leaves a record too, so "posted" means a real upload or a TikTok draft waiting in the inbox.
const posted = (j: JobSummary) => Object.values(j.published).some((r) => r.status === "published" || r.status === "needs_action");

const FILTERS = [
  {id: "all", label: "All", test: () => true},
  {id: "held", label: "Needs approval", test: (j: JobSummary) => j.held},
  {id: "ready", label: "Ready", test: (j: JobSummary) => Boolean(j.video) && !j.stale.render && !posted(j)},
  {id: "published", label: "Published", test: posted},
  {id: "failed", label: "Failed", test: (j: JobSummary) => j.status === "failed"},
] as const;

export const JobsPage: React.FC = () => {
  const {tasks, version} = useRoom();
  const jobs = useLoad(api.jobs, [version]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");
  const active = FILTERS.find((f) => f.id === filter)!;
  const list = (jobs.data ?? []).filter(active.test);
  const cur = tasks?.current ?? null;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Jobs</h1>
          <p>Every short, one folder each. Lights show script, voice, video and posting.</p>
        </div>
        <div className="seg" role="group" aria-label="Filter jobs">
          {FILTERS.map((f) => (
            <button key={f.id} aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>
      {jobs.error ? <p className="error-text">{jobs.error}</p> : null}
      {jobs.data && list.length === 0 ? (
        <div className="empty">
          <strong>{filter === "all" ? "No jobs yet" : `No jobs under “${active.label}”`}</strong>
          {filter === "all" ? "Make a short from the wire on the Today page." : "Pick another filter to see the rest."}
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Short</th>
              <th>Stages</th>
              <th className="hide-sm">Style</th>
              <th className="hide-sm">Length</th>
              <th className="hide-sm">Checks</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {list.map((j) => {
              const lights = j.status === "unreadable" ? null : stageStates(j, cur);
              return (
                <tr key={j.id} className="click" onClick={() => go(`/jobs/${j.id}`)}>
                  <td className="num dim">{j.created ? shortDate(j.created) : ""}</td>
                  <td style={{maxWidth: 520}}>
                    <a className="t" href={`#/jobs/${j.id}`} onClick={(e) => e.stopPropagation()}>
                      {j.title}
                    </a>
                    <div className="faint" style={{fontSize: "var(--s-1)"}}>
                      {j.source || "Your article"}
                    </div>
                  </td>
                  <td>{lights ? <StageLights states={lights} compact /> : null}</td>
                  <td className="hide-sm dim">{j.style ? j.style[0].toUpperCase() + j.style.slice(1) : "–"}</td>
                  <td className="hide-sm num dim">{j.frames ? tcf(j.frames, j.fps) : "Not voiced"}</td>
                  <td className="hide-sm">
                    {j.scenes ? <Checks n={j.warnings} short /> : <span className="faint">No script</span>}
                  </td>
                  <td>
                    <span className="status-word">{j.status === "unreadable" ? `Unreadable: ${j.error}` : statusText(j, cur)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
};
