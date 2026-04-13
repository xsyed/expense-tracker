/* eslint-disable no-undef */
"use strict";

const MAX_FILES = 6;
const HARD_REQUIRED = ["date", "description"];
const TARGET_OPTIONS = [
  { value: "", label: "— skip —" },
  { value: "date", label: "Date" },
  { value: "description", label: "Description" },
  { value: "amount", label: "Amount" },
  { value: "account", label: "Account" },
];

/** @type {MappingPanel[]} */
const panels = [];

// ─── Utilities ────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function capitalise(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function parseCSVLine(line) {
  const result = [];
  let current = "";
  let inQuote = false;
  for (const ch of line) {
    if (ch === '"') {
      inQuote = !inQuote;
    } else if (ch === "," && !inQuote) {
      result.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current.trim());
  return result;
}

function parseCSVHeaders(text) {
  const firstLine = (text.split("\n")[0] || "").replace(/\r$/, "");
  return parseCSVLine(firstLine);
}

function parseCSVRows(text) {
  return text
    .split("\n")
    .slice(1, 6)
    .map((l) => l.replace(/\r$/, ""))
    .filter((l) => l.trim())
    .map(parseCSVLine);
}

// ─── MappingPanel ─────────────────────────────────────────────────────────────

class MappingPanel {
  constructor(file, index) {
    this.file = file;
    this.index = index;
    this.headers = [];
    this.rows = [];
    this.rawText = "";
    this.hasHeader = true;
    this.state = "PENDING";
    this.element = null;
    this.validationFired = false;
    this.profileApplied = false;
    this.appliedProfileName = "";
  }

  async init() {
    await this._readFile();
    this.element = this._buildDOM();
    await this._checkProfiles();
    return this.element;
  }

  _readFile() {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        this.rawText = e.target.result;
        this._deriveFromRaw();
        resolve();
      };
      reader.readAsText(this.file);
    });
  }

  _deriveFromRaw() {
    if (this.hasHeader) {
      this.headers = parseCSVHeaders(this.rawText);
      this.rows = parseCSVRows(this.rawText);
    } else {
      const lines = this.rawText.split("\n").map((l) => l.replace(/\r$/, ""));
      const n = parseCSVLine(lines[0] || "").length;
      this.headers = Array.from({ length: n }, (_, i) => String(i));
      this.rows = lines
        .slice(0, 5)
        .filter((l) => l.trim())
        .map(parseCSVLine);
    }
  }

  async _checkProfiles() {
    if (!window.CSV_MAPPER_URLS.matchProfiles) return;
    try {
      const resp = await fetch(window.CSV_MAPPER_URLS.matchProfiles, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
        body: JSON.stringify({ headers: this.headers }),
        credentials: "same-origin",
      });
      if (!resp.ok) return;
      const data = await resp.json();
      const profiles = data.profiles || [];
      if (profiles.length === 0) return;

      const header = this.element.querySelector(".card-header");
      const badge = this.element.querySelector(".status-badge");

      if (profiles.length === 1) {
        this._applyProfile(profiles[0]);
      } else {
        const sel = document.createElement("select");
        sel.className = "form-select form-select-sm profile-select ms-2";
        sel.style.maxWidth = "220px";
        sel.innerHTML =
          '<option value="">Manual mapping</option>' +
          profiles.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
        sel.addEventListener("change", () => {
          const chosen = profiles.find((p) => String(p.id) === sel.value);
          if (chosen) {
            this._applyProfile(chosen);
          } else {
            this._clearProfile();
          }
        });
        header.insertBefore(sel, badge);
      }
    } catch {
      // profile matching is best-effort
    }
  }

  _applyProfile(profile) {
    if (profile.has_header !== this.hasHeader) {
      this.hasHeader = profile.has_header;
      this.element.querySelector(".headerless-toggle").checked = !this.hasHeader;
      this._deriveFromRaw();
      this._rebuildMappingBody(this.element);
    }

    const mapping = profile.mapping || {};
    this.element.querySelectorAll(".mapping-select").forEach((sel) => (sel.value = ""));

    if (mapping.date) {
      const dateSel = this.element.querySelector(`.mapping-select[data-header="${CSS.escape(mapping.date)}"]`);
      if (dateSel) dateSel.value = "date";
    }
    if (mapping.description) {
      const descSel = this.element.querySelector(`.mapping-select[data-header="${CSS.escape(mapping.description)}"]`);
      if (descSel) descSel.value = "description";
    }
    for (const col of mapping.amount || []) {
      const amtSel = this.element.querySelector(`.mapping-select[data-header="${CSS.escape(col)}"]`);
      if (amtSel) amtSel.value = "amount";
    }
    if (mapping.account) {
      const acctSel = this.element.querySelector(`.mapping-select[data-header="${CSS.escape(mapping.account)}"]`);
      if (acctSel) acctSel.value = "account";
    }

    if (profile.account_id) {
      this.element.querySelector(".account-select").value = String(profile.account_id);
    }

    this.profileApplied = true;
    this.appliedProfileName = profile.name;
    this._showProfileBadge(profile.name);
    this._renderPreview(this.element);
  }

  _showProfileBadge(name) {
    const badge = this.element.querySelector(".status-badge");
    badge.innerHTML = `<span class="badge text-bg-success">Profile: ${escapeHtml(name)}</span>`;
    badge.classList.remove("d-none");
  }

  _clearProfile() {
    this.profileApplied = false;
    this.appliedProfileName = "";
    const badge = this.element.querySelector(".status-badge");
    badge.innerHTML = "";
    badge.classList.add("d-none");
    this.element.querySelectorAll(".mapping-select").forEach((sel) => (sel.value = ""));
    this.element.querySelector(".account-select").value = "";
    this._renderPreview(this.element);
  }

  _buildDOM() {
    const card = document.createElement("div");
    card.className = "card mb-3 mapping-panel";
    card.dataset.panelIndex = this.index;

    card.appendChild(this._buildHeader());
    card.appendChild(this._buildMappingBody());

    const errDiv = document.createElement("div");
    errDiv.className = "mapping-error text-danger small d-none px-3 pb-2";
    errDiv.setAttribute("role", "alert");
    card.appendChild(errDiv);

    card.appendChild(this._buildPreviewSection());

    const resultArea = document.createElement("div");
    resultArea.className = "result-area d-none";
    card.appendChild(resultArea);

    card.appendChild(this._buildFooter());

    this._wireEvents(card);
    this._renderPreview(card);
    return card;
  }

  _buildHeader() {
    const header = document.createElement("div");
    header.className = "card-header d-flex align-items-center gap-2";
    header.innerHTML = `
      <span class="badge text-bg-secondary">File ${this.index + 1}</span>
      <span class="text-truncate fw-normal" style="max-width:300px;" title="${escapeHtml(this.file.name)}">${escapeHtml(this.file.name)}</span>
      <div class="form-check form-check-inline mb-0 ms-2">
        <input type="checkbox" class="form-check-input headerless-toggle" id="headerless-${this.index}"${this.hasHeader ? "" : " checked"}>
        <label class="form-check-label small" for="headerless-${this.index}">No header row</label>
      </div>
      <span class="ms-auto status-badge d-none"></span>
      <button type="button" class="btn-close remove-panel-btn ms-2" aria-label="Remove" title="Remove this file"></button>`;
    return header;
  }

  _buildMappingBody() {
    const optsHTML = TARGET_OPTIONS.map(
      (o) => `<option value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</option>`
    ).join("");
    const rowsHTML = this.headers
      .map(
        (h) => `
        <tr>
          <td class="align-middle ps-3"><code>${this.hasHeader ? escapeHtml(h) : `Column ${parseInt(h) + 1}`}</code></td>
          <td class="text-center align-middle text-muted" style="width:44px;">&rarr;</td>
          <td class="align-middle pe-3">
            <div class="d-flex align-items-center gap-2">
              <select class="form-select form-select-sm mapping-select" data-header="${escapeHtml(h)}">${optsHTML}</select>
              <span class="badge text-bg-danger d-none required-badge">Required</span>
            </div>
          </td>
        </tr>`
      )
      .join("");

    const body = document.createElement("div");
    body.className = "card-body p-0";
    body.innerHTML = `
      <table class="table table-borderless mb-0">
        <thead class="table-light">
          <tr>
            <th class="ps-3">CSV Column</th>
            <th class="text-center" style="width:44px;"></th>
            <th>Maps To</th>
          </tr>
        </thead>
        <tbody class="mapping-rows">${rowsHTML}</tbody>
      </table>`;
    return body;
  }

  _buildPreviewSection() {
    const el = document.createElement("div");
    el.className = "preview-section d-none";
    el.innerHTML = `
      <div class="card-header py-2">
        <small class="text-muted">Preview <span class="fw-normal">(first 5 rows)</span></small>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-striped mb-0 preview-table"></table>
      </div>`;
    return el;
  }

  _buildFooter() {
    const accountsHTML = (window.CSV_MAPPER_ACCOUNTS || [])
      .map((a) => `<option value="${escapeHtml(String(a.pk))}">${escapeHtml(a.name)}</option>`)
      .join("");

    const footer = document.createElement("div");
    footer.className = "card-footer d-flex align-items-center flex-wrap gap-3";
    footer.innerHTML = `
      <div>
        <label class="form-label mb-1 small text-muted">Account <span class="fw-normal text-muted">(optional)</span></label>
        <select class="form-select form-select-sm account-select" style="min-width:180px;">
          <option value="">— No account —</option>
          ${accountsHTML}
        </select>
      </div>
      <div class="ms-auto d-flex gap-2">
        <button type="button" class="btn btn-primary btn-sm import-btn">
          <i class="bi bi-cloud-upload me-1"></i>Import
        </button>
        <button type="button" class="btn btn-outline-secondary btn-sm download-btn">
          <i class="bi bi-download me-1"></i>Download
        </button>
      </div>`;
    return footer;
  }

  _wireEvents(card) {
    card.querySelectorAll(".mapping-select").forEach((sel) =>
      sel.addEventListener("change", (e) => this._onMappingChange(e, card))
    );
    card.querySelector(".headerless-toggle").addEventListener("change", () => this._onHeaderToggle(card));
    card.querySelector(".account-select").addEventListener("change", () => this._onAccountChange());
    card.querySelector(".import-btn").addEventListener("click", () => importPanel(this));
    card.querySelector(".download-btn").addEventListener("click", () => triggerDownload(this));
    card.querySelector(".remove-panel-btn").addEventListener("click", () => removePanel(this));
  }

  async _onAccountChange() {
    const accountId = this.element.querySelector(".account-select").value;
    if (!accountId || this.profileApplied) return;
    try {
      const resp = await fetch(window.CSV_MAPPER_URLS.matchProfiles, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
        body: JSON.stringify({ headers: this.headers, account_id: parseInt(accountId) }),
        credentials: "same-origin",
      });
      if (!resp.ok) return;
      const data = await resp.json();
      const profiles = data.profiles || [];
      if (profiles.length === 1) this._applyProfile(profiles[0]);
    } catch {
      // best-effort
    }
  }

  _onMappingChange(event, card) {
    const changed = event.target;
    if (changed.value && changed.value !== "amount") {
      card.querySelectorAll(".mapping-select").forEach((other) => {
        if (other !== changed && other.value === changed.value) {
          other.value = "";
        }
      });
    }
    if (this.profileApplied) {
      this.profileApplied = false;
      this.appliedProfileName = "";
      const badge = card.querySelector(".status-badge");
      badge.innerHTML = "";
      badge.classList.add("d-none");
    }
    if (this.validationFired) this._refreshBadges(card);
    this._renderPreview(card);
  }

  _onHeaderToggle(card) {
    this.hasHeader = !card.querySelector(".headerless-toggle").checked;
    this._deriveFromRaw();
    this._rebuildMappingBody(card);
    this.validationFired = false;
    this._renderPreview(card);
  }

  _rebuildMappingBody(card) {
    const newBody = this._buildMappingBody();
    card.querySelector(".card-body").replaceWith(newBody);
    newBody.querySelectorAll(".mapping-select").forEach((sel) =>
      sel.addEventListener("change", (e) => this._onMappingChange(e, card))
    );
  }

  getCurrentMapping() {
    if (!this.element) return {};
    const m = {};
    this.element.querySelectorAll(".mapping-select").forEach((sel) => {
      if (!sel.value) return;
      if (sel.value === "amount") {
        if (!m.amount) m.amount = [];
        m.amount.push(sel.dataset.header);
      } else {
        m[sel.value] = sel.dataset.header;
      }
    });
    return m;
  }

  validate() {
    const mapping = this.getCurrentMapping();
    const missing = HARD_REQUIRED.filter((t) => !mapping[t]);
    const amountOk = (mapping.amount?.length ?? 0) > 0;
    if (missing.length || !amountOk) {
      const labels = [...missing.map(capitalise), ...(!amountOk ? ["Amount"] : [])];
      return "Required columns not mapped: " + labels.join(", ") + ".";
    }
    return null;
  }

  _refreshBadges(card) {
    const mapping = this.getCurrentMapping();
    const missing = HARD_REQUIRED.filter((t) => !mapping[t]);
    const amountOk = (mapping.amount?.length ?? 0) > 0;
    const hasMissing = missing.length > 0 || !amountOk;
    card.querySelectorAll(".mapping-select").forEach((sel) => {
      const badge = sel.parentElement.querySelector(".required-badge");
      if (badge) badge.classList.toggle("d-none", !(sel.value === "" && hasMissing));
    });
    if (!hasMissing) {
      const errDiv = card.querySelector(".mapping-error");
      if (errDiv) errDiv.classList.add("d-none");
    }
  }

  _renderPreview(card) {
    const mapping = this.getCurrentMapping();
    const hasAmount = (mapping.amount?.length ?? 0) > 0;
    const logicalCols = [];
    if (mapping["date"]) logicalCols.push("date");
    if (mapping["description"]) logicalCols.push("description");
    if (hasAmount) logicalCols.push("_amount");
    if (mapping["account"]) logicalCols.push("account");

    const previewSection = card.querySelector(".preview-section");
    if (!logicalCols.length) {
      previewSection.classList.add("d-none");
      return;
    }

    const hdrs = this.headers;
    const headerRow = logicalCols
      .map((t) => `<th>${t === "_amount" ? "Amount" : capitalise(t)}</th>`)
      .join("");
    const bodyRows = this.rows
      .map((row) => {
        const cells = logicalCols
          .map((t) => {
            if (t === "_amount") {
              const filled = (mapping.amount || [])
                .map((col) => {
                  const idx = hdrs.indexOf(col);
                  return (idx >= 0 ? row[idx] || "" : "").trim();
                })
                .filter((v) => v);
              if (filled.length > 1) return `<td class="text-danger small">⚠ Conflict</td>`;
              return `<td>${escapeHtml(filled[0] || "")}</td>`;
            }
            const idx = hdrs.indexOf(mapping[t]);
            return `<td>${escapeHtml(idx >= 0 ? row[idx] || "" : "")}</td>`;
          })
          .join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");

    card.querySelector(".preview-table").innerHTML =
      `<thead class="table-light"><tr>${headerRow}</tr></thead><tbody>${bodyRows}</tbody>`;
    previewSection.classList.remove("d-none");
  }

  getImportFormData() {
    const fd = new FormData();
    fd.append("csrfmiddlewaretoken", window.CSRF_TOKEN);
    fd.append("csv_file", this.file);
    const mapping = this.getCurrentMapping();
    fd.append("map_date", mapping["date"] || "");
    fd.append("map_description", mapping["description"] || "");
    (mapping.amount || []).forEach((col) => fd.append("map_amount", col));
    if (mapping["account"]) fd.append("map_account_col", mapping["account"]);
    const accountId = this.element.querySelector(".account-select").value;
    if (accountId) fd.append("account_id", accountId);
    fd.append("headerless", this.hasHeader ? "false" : "true");
    return fd;
  }

  appendToBulkFormData(fd, index) {
    const prefix = `${index}_`;
    fd.append(`file_${index}`, this.file);
    const mapping = this.getCurrentMapping();
    fd.append(`${prefix}map_date`, mapping["date"] || "");
    fd.append(`${prefix}map_description`, mapping["description"] || "");
    (mapping.amount || []).forEach((col) => fd.append(`${prefix}map_amount`, col));
    if (mapping["account"]) fd.append(`${prefix}map_account_col`, mapping["account"]);
    const accountId = this.element.querySelector(".account-select").value;
    if (accountId) fd.append(`${prefix}account_id`, accountId);
    fd.append(`${prefix}headerless`, this.hasHeader ? "false" : "true");
  }

  markImporting() {
    this.state = "IMPORTING";
    const importBtn = this.element.querySelector(".import-btn");
    importBtn.disabled = true;
    importBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Importing\u2026';
    this.element.querySelector(".download-btn").disabled = true;
    this.element.querySelectorAll(".mapping-select").forEach((sel) => (sel.disabled = true));
    this.element.querySelector(".account-select").disabled = true;
    this.element.querySelector(".remove-panel-btn").disabled = true;
  }

  markSuccess(result) {
    this.state = "IMPORTED";
    const badge = this.element.querySelector(".status-badge");
    badge.innerHTML = '<span class="badge text-bg-success">Imported</span>';
    badge.classList.remove("d-none");

    const resultArea = this.element.querySelector(".result-area");
    resultArea.className = "result-area card-footer bg-success-subtle";
    resultArea.innerHTML = this._buildSuccessHTML(result);

    if (!this.profileApplied && window.CSV_MAPPER_URLS.saveProfile) {
      this._renderSavePrompt(resultArea);
    }

    this.element.querySelector(".card-body").classList.add("d-none");
    const previewSection = this.element.querySelector(".preview-section");
    if (previewSection) previewSection.classList.add("d-none");

    this.element.querySelector(".import-btn").classList.add("d-none");
    this.element.querySelector(".download-btn").disabled = false;
  }

  _renderSavePrompt(container) {
    const accountId = this.element.querySelector(".account-select").value;
    if (!accountId) return;

    const wrapper = document.createElement("div");
    wrapper.className = "mt-2 pt-2 border-top d-flex align-items-center gap-2";
    wrapper.innerHTML = `
      <span class="small text-muted">Save this mapping as a profile?</span>
      <button type="button" class="btn btn-sm btn-outline-success save-profile-btn">
        <i class="bi bi-bookmark-plus me-1"></i>Save
      </button>
      <span class="save-profile-status small d-none"></span>`;
    container.appendChild(wrapper);

    wrapper.querySelector(".save-profile-btn").addEventListener("click", () => this._saveProfile(wrapper));
  }

  async _saveProfile(wrapper) {
    const btn = wrapper.querySelector(".save-profile-btn");
    const status = wrapper.querySelector(".save-profile-status");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving\u2026';

    const mapping = this.getCurrentMapping();
    const accountId = this.element.querySelector(".account-select").value;
    const stem = this.file.name.replace(/\.csv$/i, "");

    try {
      const resp = await fetch(window.CSV_MAPPER_URLS.saveProfile, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
        body: JSON.stringify({
          headers: this.headers,
          mapping: mapping,
          account_id: accountId ? parseInt(accountId) : null,
          has_header: this.hasHeader,
          filename: stem,
        }),
        credentials: "same-origin",
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error || "Save failed.");
      }
      const data = await resp.json();
      btn.classList.add("d-none");
      status.classList.remove("d-none");
      status.innerHTML = `<i class="bi bi-check-circle text-success me-1"></i>Saved as <strong>${escapeHtml(data.name)}</strong>`;
    } catch (e) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-bookmark-plus me-1"></i>Save';
      status.classList.remove("d-none");
      status.className = "save-profile-status small text-danger";
      status.textContent = e.message || "Save failed.";
    }
  }

  _buildSuccessHTML(result) {
    const n = (count, word) => `${count} ${word}${count !== 1 ? "s" : ""}`;
    let html = `
      <p class="mb-2">
        <i class="bi bi-check-circle-fill text-success me-2"></i>
        Imported <strong>${result.total_imported}</strong> transaction${result.total_imported !== 1 ? "s" : ""}.
      </p>`;
    if (result.months && result.months.length > 0) {
      html += `
        <table class="table table-sm mb-2">
          <thead class="table-light"><tr><th>Month</th><th class="text-center">Transactions</th><th>Status</th></tr></thead>
          <tbody>`;
      for (const m of result.months) {
        const statusBadge = m.is_new
          ? '<span class="badge text-bg-success">\u2728 new</span>'
          : '<span class="badge text-bg-secondary">existing</span>';
        html += `<tr>
          <td>${escapeHtml(m.label)}</td>
          <td class="text-center">${m.count}</td>
          <td>${statusBadge}</td>
        </tr>`;
      }
      html += `</tbody></table>`;
    }
    if (result.skipped_future) {
      html += `<p class="text-warning mb-1 small"><i class="bi bi-clock me-1"></i>Skipped ${n(result.skipped_future, "future-dated row")}.</p>`;
    }
    if (result.skipped_errors) {
      html += `<p class="text-danger mb-0 small"><i class="bi bi-exclamation-triangle me-1"></i>Skipped ${n(result.skipped_errors, "row")} with parse errors.</p>`;
    }
    return html;
  }

  markError(msg) {
    this.state = "ERROR";
    const errDiv = this.element.querySelector(".mapping-error");
    errDiv.textContent = msg;
    errDiv.classList.remove("d-none");
    const importBtn = this.element.querySelector(".import-btn");
    importBtn.disabled = false;
    importBtn.innerHTML = '<i class="bi bi-cloud-upload me-1"></i>Import';
    this.element.querySelector(".download-btn").disabled = false;
    this.element.querySelectorAll(".mapping-select").forEach((sel) => (sel.disabled = false));
    this.element.querySelector(".account-select").disabled = false;
    this.element.querySelector(".remove-panel-btn").disabled = false;
  }

  get isImported() {
    return this.state === "IMPORTED";
  }

  get isPending() {
    return this.state === "PENDING" || this.state === "ERROR";
  }
}

// ─── Remove panel ─────────────────────────────────────────────────────────────

function removePanel(panel) {
  if (panel.state === "IMPORTING") return;
  const idx = panels.indexOf(panel);
  if (idx === -1) return;
  panels.splice(idx, 1);
  panel.element.remove();
  updateImportAllButton();
}

function clearAll() {
  panels.length = 0;
  document.getElementById("panels-container").innerHTML = "";
  updateImportAllButton();
}

// ─── Confirm modal ────────────────────────────────────────────────────────────

function confirmAction(message) {
  return new Promise((resolve, reject) => {
    const modalEl = document.getElementById("confirm-modal");
    const msgEl = document.getElementById("confirm-message");
    const btn = document.getElementById("confirm-proceed-btn");
    msgEl.textContent = message;
    let confirmed = false;

    function onConfirm() {
      confirmed = true;
    }

    function onHide() {
      btn.removeEventListener("click", onConfirm);
      modalEl.removeEventListener("hidden.bs.modal", onHide);
      if (confirmed) resolve();
      else reject(new Error("cancelled"));
    }

    btn.addEventListener("click", onConfirm);
    modalEl.addEventListener("hidden.bs.modal", onHide);
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  });
}

// ─── Import individual panel ──────────────────────────────────────────────────

async function importPanel(panel) {
  const err = panel.validate();
  if (err) {
    panel.validationFired = true;
    panel._refreshBadges(panel.element);
    const errDiv = panel.element.querySelector(".mapping-error");
    errDiv.textContent = err;
    errDiv.classList.remove("d-none");
    panel.element.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  try {
    await confirmAction(`Import "${panel.file.name}"?`);
  } catch {
    return;
  }

  panel.markImporting();
  updateImportAllButton();

  try {
    const resp = await fetch(window.CSV_MAPPER_URLS.import, {
      method: "POST",
      body: panel.getImportFormData(),
      credentials: "same-origin",
    });
    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
    panel.markSuccess(await resp.json());
  } catch (e) {
    panel.markError(e.message || "Import failed. Please try again.");
  }
  updateImportAllButton();
}

// ─── Import all ───────────────────────────────────────────────────────────────

async function importAll() {
  const pending = panels.filter((p) => p.isPending);
  if (!pending.length) return;

  const errors = pending.map((p) => ({ panel: p, err: p.validate() })).filter((x) => x.err);
  if (errors.length) {
    errors.forEach(({ panel: p, err }) => {
      p.validationFired = true;
      p._refreshBadges(p.element);
      const errDiv = p.element.querySelector(".mapping-error");
      errDiv.textContent = err;
      errDiv.classList.remove("d-none");
    });
    errors[0].panel.element.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  const n = pending.length;
  try {
    await confirmAction(`Import ${n} file${n !== 1 ? "s" : ""}?`);
  } catch {
    return;
  }

  pending.forEach((p) => p.markImporting());
  updateImportAllButton();

  const fd = new FormData();
  fd.append("csrfmiddlewaretoken", window.CSRF_TOKEN);
  fd.append("file_count", String(pending.length));
  pending.forEach((p, i) => p.appendToBulkFormData(fd, i));

  try {
    const resp = await fetch(window.CSV_MAPPER_URLS.bulk, {
      method: "POST",
      body: fd,
      credentials: "same-origin",
    });
    if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
    const data = await resp.json();
    const results = data.results || [];
    pending.forEach((p, i) => {
      const r = results[i];
      if (!r) p.markError("No result received.");
      else if (r.error) p.markError(r.error);
      else p.markSuccess(r);
    });
  } catch (e) {
    pending.forEach((p) => p.markError(e.message || "Import failed."));
  }
  updateImportAllButton();
}

// ─── Download ─────────────────────────────────────────────────────────────────

function triggerDownload(panel) {
  const mapping = panel.getCurrentMapping();
  const accountId = panel.element.querySelector(".account-select").value;

  const form = document.createElement("form");
  form.method = "post";
  form.action = window.CSV_MAPPER_URLS.download;
  form.enctype = "multipart/form-data";
  form.style.display = "none";

  function addHidden(name, val) {
    const el = document.createElement("input");
    el.type = "hidden";
    el.name = name;
    el.value = val;
    form.appendChild(el);
  }

  addHidden("csrfmiddlewaretoken", window.CSRF_TOKEN);

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.name = "csv_file";
  const dt = new DataTransfer();
  dt.items.add(panel.file);
  fileInput.files = dt.files;
  form.appendChild(fileInput);

  addHidden("map_date", mapping["date"] || "");
  addHidden("map_description", mapping["description"] || "");
  (mapping.amount || []).forEach((col) => addHidden("map_amount", col));
  if (mapping["account"]) addHidden("map_account_col", mapping["account"]);
  addHidden("headerless", panel.hasHeader ? "false" : "true");
  if (accountId) addHidden("account_id", accountId);

  document.body.appendChild(form);
  form.submit();
  document.body.removeChild(form);
}

// ─── File input handler ───────────────────────────────────────────────────────

async function handleFileSelect(event) {
  const files = Array.from(event.target.files || []).slice(0, MAX_FILES);
  event.target.value = "";
  if (!files.length) return;

  panels.length = 0;
  const container = document.getElementById("panels-container");
  container.innerHTML = "";

  for (let i = 0; i < files.length; i++) {
    const panel = new MappingPanel(files[i], i);
    await panel.init();
    panels.push(panel);
    container.appendChild(panel.element);
  }

  updateImportAllButton();
}

// ─── Import All button state ──────────────────────────────────────────────────

function updateImportAllButton() {
  const actionsBar = document.getElementById("panels-actions");
  const importBtn = document.getElementById("import-all-btn");
  if (panels.length === 0) {
    actionsBar.classList.add("d-none");
    return;
  }
  actionsBar.classList.remove("d-none");
  if (panels.length < 2) {
    importBtn.classList.add("d-none");
  } else {
    importBtn.classList.remove("d-none");
    importBtn.disabled = panels.filter((p) => p.isPending).length === 0;
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────

document.getElementById("csv-files").addEventListener("change", handleFileSelect);
document.getElementById("import-all-btn").addEventListener("click", importAll);
document.getElementById("clear-all-btn").addEventListener("click", clearAll);

// ─── Saved Profiles Management ────────────────────────────────────────────────

async function loadSavedProfiles() {
  const body = document.getElementById("saved-profiles-body");
  if (!body || !window.CSV_MAPPER_URLS.listProfiles) return;

  try {
    const resp = await fetch(window.CSV_MAPPER_URLS.listProfiles, { credentials: "same-origin" });
    if (!resp.ok) return;
    const data = await resp.json();
    const profiles = data.profiles || [];
    if (profiles.length === 0) {
      body.innerHTML = '<p class="text-muted small mb-0">No saved profiles yet.</p>';
      return;
    }
    body.innerHTML = `
      <table class="table table-sm table-hover mb-0">
        <thead class="table-light">
          <tr><th>Name</th><th>Account</th><th style="width:70px;"></th></tr>
        </thead>
        <tbody>
          ${profiles
            .map(
              (p) => `
            <tr data-profile-id="${p.id}">
              <td>${escapeHtml(p.name)}</td>
              <td>${p.account_name ? escapeHtml(p.account_name) : '<span class="text-muted">\u2014</span>'}</td>
              <td>
                <button type="button" class="btn btn-sm btn-outline-danger delete-profile-btn" data-id="${p.id}">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    body.querySelectorAll(".delete-profile-btn").forEach((btn) =>
      btn.addEventListener("click", () => deleteProfile(parseInt(btn.dataset.id)))
    );
  } catch {
    body.innerHTML = '<p class="text-danger small mb-0">Failed to load profiles.</p>';
  }
}

async function deleteProfile(id) {
  const url = window.CSV_MAPPER_URLS.deleteProfile.replace("{id}", String(id));
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": window.CSRF_TOKEN },
      credentials: "same-origin",
    });
    if (!resp.ok) return;
    const row = document.querySelector(`tr[data-profile-id="${id}"]`);
    if (row) row.remove();
    const tbody = document.querySelector("#saved-profiles-body tbody");
    if (tbody && tbody.children.length === 0) {
      document.getElementById("saved-profiles-body").innerHTML =
        '<p class="text-muted small mb-0">No saved profiles yet.</p>';
    }
  } catch {
    // best-effort
  }
}

document.getElementById("saved-profiles-section")?.addEventListener("show.bs.collapse", () => loadSavedProfiles());
