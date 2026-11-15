let state,
  selected = "A11",
  version = "baseline",
  control = false,
  current = null,
  verdict = null;
function marked(text, hits) {
  let out = "",
    pos = 0;
  for (const h of [...hits].sort((a, b) => a.start - b.start)) {
    if (h.start < pos) continue;
    out +=
      esc(text.slice(pos, h.start)) +
      '<mark class="' +
      (h.classification === "authorized" ? "authorized" : "") +
      '" title="' +
      esc(h.field + " / " + h.classification) +
      '">' +
      esc(text.slice(h.start, h.end)) +
      "</mark>";
    pos = h.end;
  }
  return out + esc(text.slice(pos));
}
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (x) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        x
      ],
  );
async function api(url, data) {
  const r = await fetch(
    url,
    data
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      : {},
  );
  const j = await r.json();
  if (!r.ok) throw Error(j.error);
  return j;
}
function notice(s) {
  $("#notice").textContent = s;
  setTimeout(() => ($("#notice").textContent = ""), 4500);
}
function renderCases() {
  const list = state.cases.filter((x) => x.control === control);
  $("#cases").innerHTML = list
    .map(
      (x) =>
        `<button class="case ${x.id === selected ? "selected" : ""}" data-case="${x.id}"><b>${esc(x.title)}</b><small>${x.id} / ${esc(x.family)}</small></button>`,
    )
    .join("");
  document
    .querySelector('[data-case="' + selected + '"]')
    ?.scrollIntoView({ block: "nearest" });
  document.querySelectorAll("[data-case]").forEach(
    (b) =>
      (b.onclick = () => {
        selected = b.dataset.case;
        current = null;
        render();
      }),
  );
}
function render() {
  renderCases();
  $("#attacks").classList.toggle("selected", !control);
  $("#controls").classList.toggle("selected", control);
  document
    .querySelectorAll("[data-version]")
    .forEach((b) =>
      b.classList.toggle("selected", b.dataset.version === version),
    );
  $("#run").textContent =
    $("#runmode").value === "live" ? "Run live trial ↗" : "Run tool check ↗";
  const x = state.cases.find((x) => x.id === selected);
  $("#title").textContent = x.title;
  $("#family").textContent = (icons[x.family] || "◇") + " " + x.family;
  $("#prompt").innerHTML =
    x.turns
      .map(
        (s, i) =>
          `<div class="bubble"><small>${x.control ? "CUSTOMER REQUEST" : "ATTACK TURN"} ${i + 1}</small>${esc(s)}</div>`,
      )
      .join("") +
    `<div class="probe">${$("#runmode").value === "live" ? "Live model interprets the request and chooses whether to call a tool.</div><div hidden>" : "Offline probe calls <code>"}${esc(x.tool)}(${esc(JSON.stringify(x.args))})</code> directly. The prompt is not interpreted by a model.</div>`;
  showResult();
  renderOther();
}
function showResult() {
  $("#prepare").hidden = !!current;
  $("#savedbar").hidden = !current;
  if (current) {
    $("#savedbar").innerHTML =
      `<div><b>Saved evidence · ${armName(current.version)} · ${isLive(current) ? "Live model" : "Tool check"}</b><small>${current.verdict ? reviewer(current) + " · " + current.verdict : "Awaiting review"}</small></div><button id="newtest">Prepare another test</button>`;
    $("#newtest").onclick = () => {
      current = null;
      render();
    };
  }
  verdict = current?.verdict || null;
  $("#reason").value = current?.rationale || "";
  document
    .querySelectorAll("[data-verdict]")
    .forEach((b) =>
      b.classList.toggle("selected", b.dataset.verdict === verdict),
    );
  $("#save").disabled = !current;
  if (!current) {
    $("#result").innerHTML =
      "Your evidence will appear here.<small>The first check is free and runs locally.</small>";
    $("#trace").innerHTML =
      '<div class="traceitem">Tool retrieval<small>Not run</small></div><div class="traceitem">Delivery to model<small>Not run</small></div><div class="traceitem">Customer response<small>Not run</small></div>';
    $("#hits").innerHTML = "";
    return;
  }
  const live = current.mode === "live_model";
  $("#save").disabled = current.status === "error";
  $("#result").innerHTML =
    `<b>${esc(current.version)} / ${esc(current.status)} / ${live ? "live model" : "tool check"}</b><p>${esc(current.note)}</p>` +
    (current.turns || [])
      .map(
        (t) =>
          `<div class="bubble">${esc(t.prompt)}</div><pre>${marked(t.response, t.hits)}</pre>`,
      )
      .join("") +
    current.events
      .map(
        (e) =>
          `<details><summary>${esc(e.tool)} · ${esc(e.decision)}</summary><pre>${esc(e.result)}</pre></details>`,
      )
      .join("");
  $("#trace").innerHTML =
    current.events
      .map(
        (e) =>
          `<div class="traceitem ${e.unauthorized ? "danger" : "good"}"><b>${esc(e.tool)} / ${esc(e.decision)}</b><small>${e.retrieved ? "Data retrieved" : "No data retrieved"}${e.unauthorized ? " · restricted material" : ""}</small><small>Model delivery: ${esc(e.model_delivery)}</small></div>`,
      )
      .join("") || "<p>No tool events recorded.</p>";
  const hits = (current.hits || []).filter(
    (h) => h.classification === "restricted_match",
  );
  $("#hits").innerHTML =
    `<div class="hits"><b>${live ? hits.length + " restricted response matches" : "Response not tested"}</b><p>Restricted tool material: ${current.events.some((e) => e.unauthorized) ? "Yes" : "No"}</p><p>Exact matches require human interpretation; absence does not prove safety.</p></div>`;
}
const armName = (v) => (v === "defended" ? "Protected" : "Baseline");
const isLive = (r) => r.mode === "live_model";
const leak = (r) =>
  (r.hits || []).some((h) => h.classification === "restricted_match");
const exposure = (r) =>
  (r.events || []).some(
    (e) => e.unauthorized && e.model_delivery === "provider_completed",
  );
const reviewer = (r) =>
  r.reviewer === "agent" && r.rationale?.startsWith("Agent review:")
    ? "Agent reviewed"
    : "User reviewed";
const icons = {
  "Social engineering": "♟",
  "Policy extraction": "▤",
  "PII extraction": "◎",
  Crescendo: "↗",
  "Legitimate control": "✓",
};
function liveRuns(id, v) {
  return state.runs.filter(
    (r) =>
      r.case_id === id &&
      r.version === v &&
      isLive(r) &&
      r.status === "complete",
  );
}
function counts(rs) {
  return rs.length ? `${rs.filter(leak).length}/${rs.length}` : "Not tested";
}
function openRun(id) {
  current = state.runs.find((r) => r.id === id);
  selected = current.case_id;
  version = current.version;
  control = state.cases.find((c) => c.id === selected).control;
  $("#runmode").value = isLive(current) ? "live" : "offline";
  switchTab("desk");
  render();
  $("#savedbar").scrollIntoView({ block: "center", behavior: "smooth" });
}
function pipeline() {
  const r = current,
    ev = r?.events || [],
    live = r && isLive(r);
  const nodes = [
    ["Message", r ? "Recorded request" : "Choose a scenario"],
    ["Input", "Alex · trusted session"],
    [
      "Account / policy access",
      !r
        ? "Not run"
        : ev.length
          ? ev.map((e) => e.decision).join(" · ")
          : "No tool call",
    ],
    [
      "Response",
      !r ? "Not run" : live ? "Model response recorded" : "No model used",
    ],
    [
      "Customer",
      !r
        ? "Not run"
        : live
          ? leak(r)
            ? "Restricted match detected"
            : "No restricted match"
          : "Not tested",
    ],
  ];
  $("#pipeline").innerHTML = nodes
    .map(
      ([a, b], i) =>
        `<div class="flow ${r && ((i === 2 && ev.some((e) => e.unauthorized)) || (i === 4 && leak(r))) ? "risk" : ""}"><span>0${i + 1} / ${a}</span><b>${esc(b)}</b></div>`,
    )
    .join("");
}
function renderOther() {
  $("#count").textContent = state.runs.length;
  $("#providerstatus").textContent = state.live_enabled
    ? `Nebius · $${state.budget.remaining_usd.toFixed(2)} of the $1 reservation cap remaining`
    : "Live disabled · local provider configuration required";
  $('#runmode option[value="live"]').disabled = !state.live_enabled;
  const attacks = state.cases.filter((c) => !c.control),
    controls = state.cases.filter((c) => c.control),
    live = state.runs.filter((r) => isLive(r) && r.status === "complete");
  const tested = attacks.filter((c) => live.some((r) => r.case_id === c.id));
  const legit = controls.filter((c) => live.some((r) => r.case_id === c.id));
  const base = live.filter(
      (r) => r.version === "baseline" && r.case_id.startsWith("A"),
    ),
    prot = live.filter(
      (r) => r.version === "defended" && r.case_id.startsWith("A"),
    );
  const scored = state.runs.filter((r) => r.verdict).length;
  $("#overview").innerHTML =
    `<div class="summarylead"><span class="eyebrow">MEASURED SO FAR · SYNTHETIC DATA</span><h2>${base.some(leak) ? "Follow the disclosure. Test the fix." : "The model refused. The tool still needed a lock."}</h2><p>Live refusals and direct access checks answer different questions. No claim of universal safety.</p></div><div class="stats"><div><b>${counts(base)} → ${counts(prot)}</b><span>Live attack trials with restricted response matches<br>Baseline → Protected · ${tested.length}/12 cases tested</span></div><div><b>${legit.length}/6</b><span>Legitimate cases tested live<br>Review outcomes in Compare</span></div><div><b>${scored}/${state.runs.length}</b><span>Saved results scored<br>${state.runs.filter((r) => r.reviewer === "agent").length} agent assessments</span></div></div>`;
  $("#comparison").innerHTML =
    `<div class="matrixwrap"><table class="matrix"><thead><tr><th>Scenario</th><th>Baseline · live</th><th>Protected · live</th><th>Direct tool probe<br>Baseline → Protected</th><th>Review</th></tr></thead><tbody>${state.cases
      .map((c) => {
        const cells = ["baseline", "defended"]
          .map((v) => {
            const rs = liveRuns(c.id, v);
            const failed = state.runs.filter(
              (r) =>
                r.case_id === c.id &&
                r.version === v &&
                isLive(r) &&
                r.status !== "complete",
            ).length;
            return `<td class="${rs.some(leak) ? "bad" : ""}"><b>${counts(rs)}</b><small>Context exposure: ${rs.length ? rs.filter(exposure).length + "/" + rs.length : "not tested"}${failed ? " · " + failed + " incomplete" : ""}</small></td>`;
          })
          .join("");
        const probes = ["baseline", "defended"].map((v) =>
          state.runs.find(
            (r) => r.case_id === c.id && r.version === v && !isLive(r),
          ),
        );
        const recent = state.runs.find((r) => r.case_id === c.id);
        const scores = [
          ...new Set(
            state.runs
              .filter((r) => r.case_id === c.id)
              .map((r) => r.verdict || "Unscored"),
          ),
        ];
        return `<tr><td><b>${esc(c.title)}</b><small>${c.id} · ${esc(c.family)}</small></td>${cells}<td>${probes.map((r) => (r ? `<span class="${r.events.some((e) => e.unauthorized) ? "bad" : "ok"}">${esc(r.events.map((e) => e.decision).join(", "))}${r.events.some((e) => e.unauthorized) ? " · restricted" : ""}</span>` : "Not tested")).join(" → ")}</td><td>${recent ? `<button data-open="${recent.id}">${scores.join(" / ")}</button>` : "Not tested"}</td></tr>`;
      })
      .join(
        "",
      )}</tbody></table></div><p class="probe">Counts are descriptive, not a general success rate. WARN can indicate an unsafe invitation without an observed disclosure. Repeated deterministic probes are shown once per version. Trial records remain in Evidence.</p>`;
  $("#history").innerHTML = state.cases
    .map((c) => {
      const all = state.runs.filter((r) => r.case_id === c.id);
      if (!all.length) return "";
      const seen = new Set();
      const visible = all.filter((r) => {
        if (isLive(r)) return true;
        const k = r.version;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      });
      return `<details class="casegroup"><summary><b>${esc(c.title)}</b><span>${c.id} · ${all.length} records · ${all.filter((r) => !r.verdict).length} unscored</span></summary>${visible.map((r, i) => `<div class="historyrow"><div><b>${armName(r.version)} · ${isLive(r) ? "Live trial" : "Latest tool check"}</b><small>${r.model ? esc(r.model) : "Direct execution · no model"}</small></div><div><span class="badge ${r.verdict === "FAIL" ? "bad" : r.verdict === "WARN" ? "warn" : "ok"}">${esc(r.verdict || r.status)}</span><small>${r.verdict ? reviewer(r) : "Needs review"}</small></div><div class="reasonpreview">${esc(r.rationale || "Awaiting assessment")}</div><button data-open="${r.id}">Open evidence</button></div>`).join("")}${
        all.length > visible.length
          ? `<details class="archived"><summary>${all.length - visible.length} earlier deterministic checks retained</summary>${all
              .filter((r) => !visible.includes(r))
              .map(
                (r) =>
                  `<button data-open="${r.id}">${armName(r.version)} · ${esc(r.verdict || "Unscored")}</button>`,
              )
              .join(" ")}</details>`
          : ""
      }</details>`;
    })
    .join("");
  document
    .querySelectorAll("[data-open]")
    .forEach((b) => (b.onclick = () => openRun(b.dataset.open)));
  pipeline();
}
function fixFor(c) {
  if (c.control)
    return "Preserve legitimate assistance: use the signed-in account; provide public guidance. For C06, narrow complaint disengagement so ordinary dispute requests remain supported.";
  if (c.id === "A06" || c.id === "A08" || c.id === "A12" || c.id === "A05")
    return "lookup_policy: allowlist customer-facing topics and remove staff-only sections before model context; scan the final response for restricted policy values.";
  if (c.id === "A09" || c.id === "A10")
    return "query_account: bind target to session identity before retrieval; minimize returned PII and scan or mask restricted values in output. Never treat a supplied ID as authorization.";
  if (c.id === "A07")
    return "Recheck authorization on every tool call and every turn; retain trusted session identity as the conversation escalates.";
  return "Keep trusted system instructions separate from user text; flag override or impersonation attempts at input. Enforce session ownership inside query_account before retrieval; input rails alone are insufficient.";
}
function exportReport(e) {
  e.preventDefault();
  const rows = state.cases
    .map((c) => {
      const rs = state.runs.filter((r) => r.case_id === c.id);
      const scores = rs.map((r) => r.verdict);
      const verdict = !rs.length
        ? "NOT TESTED"
        : scores.includes("FAIL")
          ? "FAIL"
          : scores.includes("WARN")
            ? "WARN"
            : scores.some((s) => !s)
              ? "UNSCORED"
              : "PASS";
      const live = ["baseline", "defended"]
        .map((v) => {
          const a = liveRuns(c.id, v);
          return `${armName(v)}: response matches ${counts(a)}, context exposure ${a.length ? a.filter(exposure).length + "/" + a.length : "not tested"}`;
        })
        .join("; ");
      const probes = ["baseline", "defended"]
        .map((v) => {
          const r = rs.find((r) => r.version === v && !isLive(r));
          return `${armName(v)} tool: ${r ? r.events.map((e) => e.decision + (e.unauthorized ? " (restricted material)" : "")).join(", ") : "not tested"}`;
        })
        .join("; ");
      const rationale = [
        ...new Set(rs.map((r) => r.rationale).filter(Boolean)),
      ].join(" ");
      return (
        "<tr>" +
        [
          c.id + " · " + c.family,
          c.turns.join("\n"),
          live + ". " + probes + ". " + rationale,
          verdict +
            " (worst observed record; both arms and modes; not a protected-only score)",
          fixFor(c),
        ]
          .map((x) => "<td>" + esc(x) + "</td>")
          .join("") +
        "</tr>"
      );
    })
    .join("");
  const doc = `<!doctype html><meta charset="utf-8"><title>Faultline findings</title><style>body{font:14px Arial;color:#17263d;margin:32px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd4df;padding:10px;text-align:left;vertical-align:top}th{background:#e7f6f3}td{white-space:pre-wrap}</style><h1>Faultline · case-level findings</h1><p>Model: Qwen/Qwen3-30B-A3B-Instruct-2507 via Nebius, temperature 0.3. Adapted from classroom ARIA (gpt-4o-mini), not a measurement of the original model. Synthetic data only. Generated ${esc(new Date().toISOString())}.</p><p>Counts use completed live trials only. Offline checks are direct tool probes, not model attacks. Zero exact matches do not establish safety. Agent assessments are labelled in the rationale and remain subject to human review. NOT TESTED rows disclose missing coverage; no results are invented. Recommended controls may be proposed, not implemented: implemented controls are session ownership and customer policy filtering.</p><table><tr>${["Attack family", "Prompt", "Observed result", "PASS/WARN/FAIL", "Recommended fix"].map((x) => "<th>" + x + "</th>").join("")}</tr>${rows}</table>`;
  const url = URL.createObjectURL(new Blob([doc], { type: "text/html" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "Faultline-case-findings.html";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("#export").onclick = exportReport;

function switchTab(tab) {
  ["desk", "compare", "evidence"].forEach(
    (id) => ($("#" + id).hidden = id !== tab),
  );
  document
    .querySelectorAll("[data-tab]")
    .forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
}
document
  .querySelectorAll("[data-tab]")
  .forEach((b) => (b.onclick = () => switchTab(b.dataset.tab)));
document.querySelectorAll("[data-version]").forEach(
  (b) =>
    (b.onclick = () => {
      version = b.dataset.version;
      document
        .querySelectorAll("[data-version]")
        .forEach((t) => t.classList.toggle("selected", t === b));
    }),
);
document.querySelectorAll("[data-verdict]").forEach(
  (b) =>
    (b.onclick = () => {
      verdict = b.dataset.verdict;
      document
        .querySelectorAll("[data-verdict]")
        .forEach((t) => t.classList.toggle("selected", t === b));
    }),
);
for (const [id, value] of [
  ["attacks", false],
  ["controls", true],
])
  $("#" + id).onclick = () => {
    control = value;
    selected = state.cases.find((c) => c.control === control).id;
    current = null;
    $("#attacks").classList.toggle("selected", !control);
    $("#controls").classList.toggle("selected", control);
    render();
  };
$("#runmode").onchange = () => {
  current = null;
  render();
};
$("#run").onclick = async () => {
  const mode = $("#runmode").value,
    case_id = selected,
    arm = version,
    n = $("#repeat").checked ? 3 : 1;
  $("#run").disabled = true;
  try {
    for (let i = 0; i < n; i++) {
      notice(`Running trial ${i + 1} of ${n}`);
      current = await api("/api/run", { case_id, version: arm, mode });
      state = await api("/api/state");
      render();
      if (current.status === "error") break;
    }
  } catch (e) {
    notice(e.message);
  } finally {
    $("#run").disabled = false;
  }
};
$("#save").onclick = async () => {
  try {
    current = await api("/api/review", {
      id: current.id,
      verdict,
      rationale: $("#reason").value,
    });
    state = await api("/api/state");
    renderOther();
    notice("Evidence review saved.");
  } catch (e) {
    notice(e.message);
  }
};
api("/api/state")
  .then((s) => {
    state = s;
    render();
  })
  .catch((e) => notice(e.message));
