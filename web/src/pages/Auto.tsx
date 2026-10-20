import React, {useEffect, useState} from "react";
import {api, type AutoSettings} from "../api";
import {useRoom} from "../App";
import {Light, Switch} from "../components/ui";
import {useLoad} from "../lib";

export const AutoPage: React.FC = () => {
  const {meta, version, refreshTasks} = useRoom();
  const auto = useLoad(api.auto, [version]);
  const [form, setForm] = useState<AutoSettings | null>(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (auto.data && !form) setForm(auto.data.settings);
  }, [auto.data, form]);

  if (!form || !auto.data || !meta) return <p className="faint">Loading…</p>;

  const set = (patch: Partial<AutoSettings>) => {
    setForm({...form, ...patch});
    setSaved("");
  };
  const save = async (next = form) => {
    setError("");
    try {
      const res = await api.saveAuto(next);
      auto.setData(res);
      setForm(res.settings);
      setSaved("Saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const enabledTargets = meta.targets.filter((t) => t.enabled);
  const next = auto.data.next_run ? new Date(auto.data.next_run) : null;

  return (
    <div className="measure">
      <div className="page-head">
        <div>
          <h1>Auto mode</h1>
          <p>Make one short a day from the top story, without you pressing anything.</p>
        </div>
      </div>

      <div className="switch-row">
        <Light s={form.enabled ? "ready" : "off"} />
        <div className="msg">
          <strong>{form.enabled ? "Auto mode is on" : "Auto mode is off"}</strong>
          <div className="dim" style={{fontSize: "var(--s-1)"}}>
            {form.enabled && next
              ? `Next run ${next.toLocaleString(undefined, {weekday: "short", hour: "2-digit", minute: "2-digit"})}`
              : "Turn it on to schedule a daily run."}
            {auto.data.state.last_run_date ? ` · last ran ${auto.data.state.last_run_date}` : ""}
          </div>
        </div>
        <Switch
          label="Auto mode"
          checked={form.enabled}
          onChange={(enabled) => {
            const nextForm = {...form, enabled};
            setForm(nextForm);
            void save(nextForm);
          }}
        />
      </div>

      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className="field" style={{maxWidth: 200}}>
          <label className="label" htmlFor="auto-time">
            Daily at
          </label>
          <input id="auto-time" type="time" value={form.time} onChange={(e) => set({time: e.target.value})} />
          <span className="help">This machine's local time.</span>
        </div>

        <fieldset className="choice" style={{border: 0, padding: 0, margin: 0}}>
          <legend className="dim" style={{fontSize: "var(--s-1)", fontWeight: 500, marginBottom: 8}}>
            When the video is ready
          </legend>
          <label>
            <input type="radio" name="mode" checked={form.mode === "hold"} onChange={() => set({mode: "hold"})} />
            <span>
              Hold it for my approval
              <small>It waits under Jobs → Needs approval, and Discord gets a preview if the webhook is set.</small>
            </span>
          </label>
          <label>
            <input type="radio" name="mode" checked={form.mode === "publish"} onChange={() => set({mode: "publish"})} />
            <span>
              Publish it automatically
              <small>Posts to the targets below as soon as it renders. Fact warnings don't stop it, so read them afterwards.</small>
            </span>
          </label>
        </fieldset>

        {form.mode === "publish" ? (
          <fieldset style={{border: 0, padding: 0, margin: 0, display: "grid", gap: 10}}>
            <legend className="dim" style={{fontSize: "var(--s-1)", fontWeight: 500, marginBottom: 8}}>
              Publish to
            </legend>
            {enabledTargets.map((t) => {
              const all = form.targets.length === 0;
              const on = all || form.targets.includes(t.platform);
              return (
                <label className="check" key={t.platform}>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={(e) => {
                      const current = all ? enabledTargets.map((x) => x.platform) : form.targets;
                      set({targets: e.target.checked ? [...current, t.platform] : current.filter((p) => p !== t.platform)});
                    }}
                  />
                  {t.platform === "export" ? "Export folder" : t.platform === "youtube" ? `YouTube Shorts (${t.privacy})` : "TikTok (inbox draft)"}
                </label>
              );
            })}
            <label className="check">
              <input type="checkbox" checked={form.dry_run} onChange={(e) => set({dry_run: e.target.checked})} />
              Dry run: record what would be posted, upload nothing
            </label>
          </fieldset>
        ) : null}

        {error ? <p className="error-text">{error}</p> : null}
        <div className="row">
          <button className="btn primary" type="submit">
            Save
          </button>
          <button
            className="btn"
            type="button"
            onClick={() =>
              void api.autoRunNow().then(
                (res) => {
                  auto.setData(res);
                  refreshTasks();
                  setSaved("Started; watch the tally");
                },
                (e) => setError(String(e.message ?? e)),
              )
            }
          >
            Run it now
          </button>
          {saved ? <span className="dim">{saved}</span> : null}
        </div>
      </form>

      <section style={{marginTop: 40}}>
        <div className="head">
          <h2>How it runs</h2>
        </div>
        <dl className="facts">
          <dt>Runs while</dt>
          <dd>this app is running. On a server, keep `technews web` running as a service.</dd>
          <dt>Missed a run</dt>
          <dd>If the app starts after the set time, it runs once that day. Days it never runs are skipped.</dd>
          <dt>Never twice</dt>
          <dd>The day is recorded before the run starts, so restarts don't repeat it.</dd>
          <dt>Task Scheduler</dt>
          <dd>If Windows Task Scheduler also runs `technews daily`, turn one of them off or you'll get two videos a day.</dd>
        </dl>
      </section>
    </div>
  );
};
