---
name: Byte Brief control room
description: The web control room for the Tech News Shorts pipeline, run like a news show's rundown.
colors:
  bg: "#16181d"
  deep: "#111317"
  panel: "#1c1f25"
  raised: "#24272f"
  hover: "#2a2e37"
  rule: "#2c3038"
  rule-strong: "#3b404b"
  rule-hover: "#4a505c"
  monitor-black: "#0a0b0e"
  text: "#e8eaed"
  dim: "#aab0ba"
  faint: "#8a919c"
  ink-on-white: "#121419"
  live: "#e5322d"
  live-ink: "#ff6a64"
  standby: "#f2b233"
  ready: "#2fb463"
  link: "#8fc0f4"
  slug-headline: "#7fb3ff"
  slug-stat: "#c9a2f2"
  slug-icon: "#5fd4c8"
  slug-versus: "#f59e7a"
  slug-bullets: "#b8d86b"
  slug-outro: "#aab0ba"
typography:
  headline:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "1.3125rem"
    fontWeight: 600
    lineHeight: 1.2
  body-large:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.45
  body-small:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Barlow Condensed, Barlow, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.08em"
  timecode:
    fontFamily: "Barlow Condensed, Barlow, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1
    fontFeature: "tnum"
  mono:
    fontFamily: "ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  tick: "3px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  pill: "13px"
  round: "50%"
components:
  button:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "34px"
  button-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.text}"
  button-primary:
    backgroundColor: "{colors.text}"
    textColor: "{colors.ink-on-white}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "34px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.dim}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "34px"
  button-small:
    padding: "0 10px"
    height: "28px"
  input:
    backgroundColor: "{colors.deep}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "7px 10px"
    height: "36px"
  tally:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.dim}"
    rounded: "{rounded.md}"
    padding: "0 14px 0 12px"
    height: "36px"
  light:
    size: "10px"
    rounded: "{rounded.round}"
  slug:
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "3px 8px 2px"
  monitor:
    backgroundColor: "{colors.monitor-black}"
    rounded: "{rounded.lg}"
    padding: "10px"
  program-bar:
    backgroundColor: "{colors.deep}"
    textColor: "{colors.dim}"
    height: "60px"
    padding: "0 24px"
---

# Design System: Byte Brief control room

## Overview

**Creative North Star: "The Producer's Rundown"**

The web app is a broadcast control room for one person. Today's story is a rundown: scenes are timed segments with a start, a length and a back-time in frame timecode (m:ss:ff), and a tally light in the program bar shows what is live. The ground is control-room graphite, text is monitor white, and colour is reserved for state. Data sits in ruled rows and timecode columns. It does not float on cards.

Density is working density: a sticky 60px program bar, a wide main column of ruled rows, and a sticky right rail holding the program monitor (the video at 9:16) and its panels. Lights are the one state vocabulary across the app (bar tally, stage lights per job, fact-check counts, queue rows, publish results, health checks), so a glance anywhere reads the same way. Barlow carries the UI. Barlow Condensed in caps is the broadcast voice for labels, slugs, stage names and timecode.

The rendered shorts in `video/` (Remotion) are a separate visual system and are not covered here.

**Key Characteristics:**
- Graphite tonal layers (deep, bg, panel, raised) separated by 1px rules, not shadows.
- Tally lights own colour: red live, amber standby or stale, green ready, dark outline off.
- Frame timecode with tabular numerals wherever time appears.
- Scene slugs colour-coded by visual type (headline, stat, icon, versus, bullets, outro).
- Bordered containers only for instruments: the monitor, the stage bar, form controls.

## Colors

Near-neutral graphite with a cool cast, three saturated tally colours, and a muted six-hue slug set that only labels scene types.

### Primary
- **Live Red** (`live`): the on-air state. It marks a pulsing live light while a render or publish runs, the solid failed light, the progress meter fill, and the live banner tint. The one non-state red is the antenna dot on the Byte mark, which is the world's own tally light. Its brighter **Live Ink** (`live-ink`) is the readable red for text on graphite: the ON AIR tally text, error text, the current scene number, and the timeline playhead.

### Secondary
- **Standby Amber** (`standby`): queued, running a non-render stage, stale and needing a re-run, estimated timings, warnings, held for approval, and the unsaved-edits save bar. It also highlights numbers in the source article, so facts can be checked against the script, and it is the focus ring colour, a deliberate choice because amber reads clearly on graphite.
- **Ready Green** (`ready`): done and current. Ready lights, the on state of switches, the ready banner.

### Tertiary
- **Slug hues** (`slug-headline` blue, `slug-stat` violet, `slug-icon` teal, `slug-versus` coral, `slug-bullets` lime, `slug-outro` grey): one per visual type. They appear only on slugs, timeline segments and the icon-picker preview, mixed into the panel with `color-mix` (16% for slug fills, 26 to 42% for timeline segments).
- **Wire Blue** (`link`): inline links, such as article sources. Hover lightens it.

### Neutral
- **Deep Graphite** (`deep`): the program bar, input wells, log and article bodies, the scrollbar track.
- **Control-Room Graphite** (`bg`): the page ground.
- **Panel Graphite** (`panel`): the tally body, stage bar, open scene, row hover fill, and checked choices. The contract specified a slightly warmer panel; the built value is the one recorded here.
- **Raised Graphite** (`raised`) and **Hover Graphite** (`hover`): button rest and hover.
- **Rule** (`rule`) and **Strong Rule** (`rule-strong`): row dividers, and control or section-head borders. **Rule Hover** (`rule-hover`) is the border on hover for buttons and inputs.
- **Monitor Black** (`monitor-black`): the program monitor's bezel. Pure black sits behind the video itself.
- **Monitor White** (`text`), **Dim** (`dim`), **Faint** (`faint`): the three text levels. Faint is the floor for help text, rank numbers and placeholders.

### Named Rules
**The Tally Owns Colour Rule.** Saturated colour means state. Red is live or failed, amber is standby, stale or warning, and green is ready. Never use these hues for decoration or emphasis. The only brand use is the red antenna dot on the Byte mark, which is itself a tally. Every other surface stays graphite and white.

**The One Light Rule.** Every stage or task state renders as the same 10px light (off, ready, standby, live, failed). Add new state displays as lights plus words, never as new badge styles.

**The Slug Palette Is Closed Rule.** The six slug hues are for scene visual types only. A new visual type gets a new slug token and nothing else does.

## Typography

**Display Font:** none. The app has no display tier.
**Body Font:** Barlow (with Segoe UI, system-ui), self-hosted at 400, 500, 600 and 700.
**Label/Mono Font:** Barlow Condensed (with Barlow) at 600 and 700, for broadcast labels and timecode. A system monospace stack is used only for raw logs.

**Character:** Barlow is plain and slightly technical, a workstation face. Barlow Condensed in tracked caps reads as console engraving and the lower-thirds of a broadcast.

### Hierarchy
- **Headline** (600, 1.75rem, 1.2, -0.01em): page h1, one per page.
- **Title** (600, 1.3125rem, 1.2): h2-level content titles.
- **Body large** (600, 1.0625rem, 1.3): story titles on the wire, the brand, empty-state heads.
- **Body** (400, 0.9375rem, 1.45): default UI and narration text. Article and summary text is capped at 75 to 78ch.
- **Body small** (0.8125rem): meta, help, notes, queue, banners, field labels (500).
- **Label** (Barlow Condensed 700, 13 to 15px, 0.07 to 0.1em, uppercase): section heads, table and rundown headers, the tally word, monitor labels, stage names, slugs.
- **Timecode** (Barlow Condensed 600, 15 to 22px, tabular numerals): rundown start, length and back-time, the run-time foot, the timescale, the monitor readout, the clock, the tally elapsed time.

### Named Rules
**The Condensed Means Console Rule.** Barlow Condensed is used only for caps labels, rank and scene numbers, and timecode. It is never used for sentences, titles or body copy.

**The Frame Timecode Rule.** Program time is shown as m:ss:ff at 30fps (frames, not tenths), always with tabular numerals. The only other formats are wall-clock ones: the tally's elapsed m:ss and the bar clock's 24-hour HH:MM:SS.

## Layout

- **Shell:** a sticky program bar, 60px tall on the deep ground (brand, tabs, then the tally and clock pushed to the right). A notices strip sits under it. The page is centred at a 1480px max width with padding 28px 28px 96px.
- **Columns:** a main column with a sticky 380px right rail (400px on the job page, where the rail is not sticky), with a 32px gap. The side rail stacks its sections at 28px. Sections stack at 32px. Single-column forms are capped at 640 to 680px.
- **Rows:** wire, queue, table, checks and rundown rows are grids separated by 1px rules, with 11 to 14px vertical padding. The rundown grid is number, slug, screen, narration, start, length, back, chevron.
- **Rhythm:** the gaps actually used are 6, 8, 10, 12, 14, 16, 24, 28 and 32px. No formal spacing scale exists.
- **At 1100px or narrower:** one column. On the job page the monitor moves above the rundown, and a deck strip replaces the On Deck rail on Today.
- **At 760px or narrower:** the bar wraps, the clock hides, and the tabs become a scrollable 42px row. The page padding drops to 20px 16px. Rundown rows reflow into named areas, with "Length" and "Back" labels drawn in the caps label style. The stage bar stacks.

## Elevation & Depth

Depth comes from tonal layers (deep, bg, panel, raised) and 1px rules. Shadows are rare and always have a job.

### Shadow Vocabulary
- **Tab underline** (`box-shadow: inset 0 -2px 0 var(--text)`): marks the current program-bar tab.
- **Live glow** (`box-shadow: 0 1px 6px rgba(229, 50, 45, 0.7)`): only on a live light, together with its 1.6s pulse.
- **Save bar lift** (`box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45)`): only on the sticky unsaved-edits bar, the one element that floats over content.

### Named Rules
**The Rules Not Shadows Rule.** Separate rows and regions with 1px `rule` or `rule-strong` lines and a step in graphite. A new shadow needs a reason as specific as "it floats over scrolling content".

## Shapes

Shapes are small and squared-off. Controls, banners, inputs and slots use a 6px radius. Instrument containers (the monitor, stage bar, switch row, save bar, deck strip, empty state) use 8px. Slugs, the video frame and skeletons use 4px, and timeline segments 3px. Round shapes are reserved for lights, the switch thumb, the switch track (13px) and the tab count pill. Borders are 1px throughout. The only dashed border is the empty state.

## Components

### Buttons
Compact console buttons.
- **Shape:** 6px radius, 34px tall, 28px for small. Barlow 600 at 14px.
- **Default:** raised graphite with a strong-rule border. Hover shifts to hover graphite with the rule-hover border.
- **Primary:** a monitor-white fill with near-black text. Hover goes to pure white. Use it for the one main action in a region.
- **Quiet:** transparent with dim text. Hover gains the raised fill and a border. Use it for back links and tertiary actions.
- **Disabled:** 0.45 opacity with a not-allowed cursor. A busy button carries a spinning icon.

### Segmented control
A strong-rule outline with 1px internal dividers and 32px buttons. The pressed segment takes the raised fill and white text. It is used for filters.

### Inputs / Fields
- **Style:** a deep-graphite well with a strong-rule border and 6px radius, at least 36px tall.
- **Focus:** the border shifts to dim. Keyboard focus adds a 2px amber outline.
- **Field:** a dim 500 small label with an optional tabular counter (amber when full) and faint help text below.
- **Switch:** a 46x26 track. When on, it takes a green border, a green-tinted fill and a green thumb.
- **Choice:** bordered radio rows. The checked row gets a dim border and the panel fill.

### Navigation
Program-bar tabs are dim Barlow 500 text over the full bar height. The current tab is white with a 2px inset underline. An amber count pill marks items held for approval.

### Tally (signature)
A 36px outlined slot in the program bar: a light, the word (OFF AIR, STANDBY, ON AIR) in caps label type, the current stage and title, elapsed time, and a 2px progress meter along the bottom edge. Standby tints the slot amber. On air gives it a red border and a faint red vertical gradient.

### Lights and stage lights (signature)
A 10px circle. Off is a 1.5px strong-rule outline. Ready is green, standby amber, and failed solid red. Live is bright red with a glow and a 1.6s opacity pulse, which is removed under reduced motion. Stage lights show Script, Voice, Video and Posted. They run as a bare row in tables and as labelled lights in panels.

### Rundown (signature)
The job page's back-timed table. A stage bar sits above it (Script, Voice, Video cells, each with a light, state and controls), then a proportional timeline of scene segments in slug colours with a Live Ink playhead, then the rows. The open scene takes the panel fill and expands into an inline editor (a visual block on the bg ground). Estimated timings show in amber.

### Slugs
Caps label type at 13px on a 16% mix of the type's hue, with 4px radius.

### Monitor
A monitor-black bezel (8px radius) around a 9:16 video. It has a caps label row with the frame-timecode readout at right, and a foot row with controls.

### Banners and warnings
Banners use a tally-tinted fill (8 to 10%) with a matching border and light text, in three variants (standby, live, ready). Warnings are amber-tinted rows with an amber icon. Notices under the bar use a dark red ground.

## Do's and Don'ts

### Do:
- **Do** show every pipeline state with the 10px light plus a word, using the five states off, ready, standby, live and failed.
- **Do** put lists of data in 1px ruled rows with a panel fill on hover. Reserve bordered containers for the monitor, stage controls and form controls.
- **Do** show program time as m:ss:ff frame timecode in Barlow Condensed with tabular numerals.
- **Do** head each section with condensed caps (15px, 0.08em) over a strong rule, with actions to the right.
- **Do** keep warnings and the source article visible in the job rail wherever publishing is decided.
- **Do** honour reduced motion. The live pulse is the only looping state animation and it switches off.

### Don't:
- **Don't** use red, amber or green for anything except state, the amber focus ring and article number highlights, and the red antenna dot of the Byte mark.
- **Don't** wrap rows of data in floating cards or a dark card dashboard. Data lives in ruled rows and timecode columns.
- **Don't** set sentences or titles in Barlow Condensed.
- **Don't** add shadows for depth. Step the graphite and draw a rule instead.
- **Don't** use slug hues outside scene-type labelling.
