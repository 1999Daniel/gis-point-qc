"use strict";

(() => {
  const el = (id) => document.getElementById(id);
  const ui = {
    form: el("check-form"), file: el("file-input"), fileTitle: el("file-title"),
    fileDetail: el("file-detail"), crs: el("crs"), categories: el("categories"),
    demo: el("is-demo"), check: el("check-button"), checkLabel: el("check-button-label"),
    status: el("service-status"), normal: el("normal-sample"), issues: el("issues-sample"),
    notice: el("notice"), empty: el("empty-state"), loading: el("loading-state"),
    content: el("result-content"), tag: el("result-tag"), panel: el("results-panel"),
    summary: el("result-summary"), overview: el("result-overview"), tbody: el("issues-body"),
    table: el("table-scroll"), count: el("table-count"), noIssues: el("no-issues"),
    more: el("show-more"), notes: el("notes-content"), subtitle: el("result-subtitle"),
  };
  const state = {meta: null, file: null, response: null, busy: false, filter: "all", visible: 100};
  const formatNumber = (value) => Number(value || 0).toLocaleString("zh-CN");
  const setText = (node, value) => { node.textContent = String(value ?? ""); };
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) setText(element, text);
    if (className) element.className = className;
    return element;
  };

  function clearResult() {
    state.response = null;
    state.filter = "all";
    state.visible = 100;
    ui.content.hidden = true;
    ui.tag.hidden = true;
    ui.empty.hidden = false;
    ui.notice.hidden = true;
    ui.loading.hidden = true;
    ui.tbody.replaceChildren();
    setText(ui.subtitle, "问题定位到行，修改建议落实到字段");
    document.querySelectorAll(".filter").forEach((button) => {
      const active = button.dataset.filter === "all";
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function notice(message) {
    setText(ui.notice, message);
    ui.notice.hidden = false;
  }

  function setBusy(busy) {
    state.busy = busy;
    [ui.file, ui.crs, ui.categories, ui.demo].forEach((control) => { control.disabled = busy; });
    [ui.check, ui.normal, ui.issues].forEach((button) => { button.disabled = busy || !state.meta; });
    ui.panel.setAttribute("aria-busy", String(busy));
    setText(ui.checkLabel, busy ? "检查中…" : state.meta ? "开始检查" : "检查服务未连接");
    if (busy) {
      ui.empty.hidden = true;
      ui.loading.hidden = false;
      ui.content.hidden = true;
    } else {
      ui.loading.hidden = true;
      ui.empty.hidden = Boolean(state.response);
    }
  }

  function selectFile(file, demo = false) {
    clearResult();
    state.file = file || null;
    ui.demo.checked = demo;
    if (state.meta) setText(ui.status, file ? "文件已选择，等待检查" : "请选择文件或使用模拟样例");
    if (!file) {
      setText(ui.fileTitle, "选择 CSV 或 Excel 文件");
      setText(ui.fileDetail, "原始文件保持不变，检查在本机完成");
      return;
    }
    setText(ui.fileTitle, file.name);
    const size = file.size < 1024 ? `${file.size} B` : file.size < 1024 * 1024 ? `${(file.size / 1024).toFixed(1)} KiB` : `${(file.size / 1024 / 1024).toFixed(2)} MiB`;
    setText(ui.fileDetail, `${size} · ${demo ? "模拟样例数据" : "已选择本地文件"}`);
  }

  async function apiJSON(response) {
    let body;
    try { body = await response.json(); }
    catch { throw new Error("检查服务未返回有效结果，请确认本地服务正在运行。"); }
    if (!response.ok || body.error) throw new Error(body.error || `请求未完成（${response.status}），请稍后重试。`);
    return body;
  }

  function asBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    const parts = [];
    // 分块转换，避免较大文件触发函数参数数量限制。
    for (let index = 0; index < bytes.length; index += 8192) {
      parts.push(String.fromCharCode(...bytes.subarray(index, index + 8192)));
    }
    return btoa(parts.join(""));
  }

  function validate() {
    if (!state.file) throw new Error("请先选择一个 CSV / XLSX 文件，或使用模拟样例。");
    if (!/\.(csv|xlsx)$/i.test(state.file.name)) throw new Error("目前支持 .csv 和 .xlsx 文件，请使用模板整理后再检查。");
    const maxBytes = state.meta?.limits?.max_bytes || 5 * 1024 * 1024;
    if (state.file.size > maxBytes) throw new Error(`文件超过 ${(maxBytes / 1024 / 1024).toFixed(0)} MiB 限制，请拆分后检查。`);
    if (!state.file.size) throw new Error("所选文件为空，请检查文件内容。");
    const categories = [...new Set(ui.categories.value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean))];
    if (!categories.length) throw new Error("请至少填写一个允许的分类，多个分类用逗号分隔。");
    return categories;
  }

  async function checkFile() {
    if (state.busy || !state.meta) return;
    clearResult();
    let categories;
    try { categories = validate(); }
    catch (error) { notice(error.message); return; }
    setBusy(true);
    try {
      const content = await state.file.arrayBuffer();
      const response = await fetch("/api/check", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-QC-Token": state.meta.token},
        body: JSON.stringify({filename: state.file.name, content_base64: asBase64(content), crs: ui.crs.value, allowed_categories: categories, is_demo: ui.demo.checked}),
      });
      const data = await apiJSON(response);
      if (!data.result || !Array.isArray(data.result.issues)) throw new Error("检查结果格式不完整，请重新运行检查。");
      state.response = data;
      renderResult(data.result);
      setText(ui.status, "检查完成，原始文件未修改");
    } catch (error) {
      notice(error instanceof TypeError ? "无法连接本地服务，请确认启动窗口仍在运行后重试。" : error.message);
      setText(ui.status, "检查未完成，请查看右侧提示");
    } finally { setBusy(false); }
  }

  function renderResult(result) {
    const summary = result.summary;
    ui.content.hidden = false;
    ui.empty.hidden = true;
    ui.tag.hidden = false;
    const problems = Number(summary.issue_count) > 0;
    const pending = summary.status === "待核实";
    setText(ui.tag, summary.status || (problems ? "发现问题" : "基础检查完成"));
    ui.tag.classList.toggle("problem", problems || pending);
    setText(ui.subtitle, `${result.filename} · ${result.is_demo ? "模拟数据" : "数据来源待核实"}`);
    ui.summary.replaceChildren();
    [
      ["检查数据", summary.total_rows, "行", ""],
      ["涉及数据行", summary.affected_rows, "行", ""],
      ["错误", summary.error_count, "项", "stat-error"],
      ["提示", summary.warning_count, "项", "stat-warning"],
    ].forEach(([label, value, unit, className]) => {
      const card = node("div", undefined, `stat ${className}`);
      const number = node("strong", formatNumber(value), "stat-value");
      card.append(node("span", label, "stat-label"), number, node("span", unit, "stat-unit"));
      ui.summary.append(card);
    });
    ui.overview.replaceChildren();
    ui.overview.append(node("strong", problems ? `发现 ${formatNumber(summary.issue_count)} 项问题。` : pending ? "当前结果待核实。" : "当前检查范围内未发现问题。"));
    ui.overview.append(document.createTextNode(problems ? " 建议先处理错误，再逐项核实提示；同一行可能包含多项问题。" : pending ? " 请核对坐标系声明及有效数据行，完成后重新检查。" : " 结果仅代表基础规则检查，实际位置与业务适用性仍需确认。"));
    if (summary.ignored_blank_rows) ui.overview.append(node("span", ` 已忽略 ${formatNumber(summary.ignored_blank_rows)} 个空行。`));
    renderIssues();
    ui.notes.replaceChildren();
    ui.notes.append(node("p", `生成时间：${result.generated_at || "—"}`));
    ui.notes.append(node("p", `坐标系声明：${result.crs || "未声明"}；数据性质：${result.is_demo ? "模拟 / 教学样例" : "来源待业务核实"}`));
    const hash = node("p", `文件 SHA-256：${result.sha256 || "—"}`, "hash");
    ui.notes.append(hash);
    if (Array.isArray(result.notes) && result.notes.length) {
      const list = node("ul");
      result.notes.forEach((note) => list.append(node("li", note)));
      ui.notes.append(list);
    }
    if (Array.isArray(result.rules) && result.rules.length) {
      ui.notes.append(node("p", `规则：${result.rules.map((rule) => `${rule.code} ${rule.title}`).join("；")}`));
    }
  }

  function renderIssues() {
    const allIssues = state.response?.result.issues || [];
    const selected = allIssues.filter((issue) => state.filter === "all" || issue.severity === state.filter);
    const visible = selected.slice(0, state.visible);
    ui.tbody.replaceChildren();
    const fragment = document.createDocumentFragment();
    visible.forEach((issue) => {
      const tr = node("tr");
      const position = node("td");
      position.append(node("span", issue.row ? `第 ${issue.row} 行` : "文件级", "cell-main"));
      position.append(node("span", `字段：${issue.field || "—"}`, "cell-detail"));
      if (issue.id !== undefined && issue.id !== null && String(issue.id)) position.append(node("span", `ID：${issue.id}`, "cell-detail"));
      const rule = node("td");
      const error = issue.severity === "error";
      rule.append(node("span", error ? "错误" : "提示", `severity ${error ? "error" : "warning"}`));
      rule.append(node("span", issue.code, "rule-code"));
      const description = node("td");
      description.append(node("span", issue.message, "cell-main"));
      if (issue.value !== undefined && issue.value !== null && String(issue.value)) {
        const value = String(issue.value);
        const valueNode = node("span", `原值：${value.length > 160 ? `${value.slice(0, 160)}…` : value}`, "cell-detail");
        valueNode.title = value;
        description.append(valueNode);
      }
      const suggestion = node("td", issue.suggestion);
      tr.append(position, rule, description, suggestion);
      fragment.append(tr);
    });
    ui.tbody.append(fragment);
    ui.table.hidden = selected.length === 0;
    ui.noIssues.hidden = selected.length !== 0;
    setText(ui.noIssues, allIssues.length ? "当前筛选下没有问题。" : state.response?.result.summary.status === "待核实" ? "未发现基础字段问题，但仍有待核实条件，详见检查范围与数据记录。" : "当前检查范围内未发现问题，可下载完整报告存档。");
    setText(ui.count, selected.length ? `共 ${formatNumber(selected.length)} 项，显示 ${formatNumber(visible.length)} 项 · 行号对应原始表格（含表头）` : "问题清单");
    ui.more.hidden = visible.length >= selected.length;
    if (!ui.more.hidden) setText(ui.more, `显示更多（剩余 ${formatNumber(selected.length - visible.length)} 项）`);
  }

  function download(content, type, suffix) {
    if (!state.response) return;
    const base = (state.response.result.filename || "points").replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]/g, "_");
    const blob = new Blob([content], {type});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${base}-${suffix}`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  async function loadSample(kind) {
    if (state.busy || !state.meta) return;
    clearResult();
    setBusy(true);
    let loaded = false;
    try {
      const response = await fetch(`/api/sample?kind=${encodeURIComponent(kind)}&format=csv`);
      if (!response.ok) { await apiJSON(response); return; }
      const bytes = await response.arrayBuffer();
      ui.file.value = "";
      selectFile(new File([bytes], `${kind}.csv`, {type: "text/csv"}), true);
      ui.crs.value = "WGS84";
      ui.categories.value = (state.meta.default_categories || ["学校", "医疗", "交通", "文体", "公共服务"]).join(",");
      loaded = true;
    } catch (error) {
      notice(error instanceof TypeError ? "样例未能加载，请确认本地服务仍在运行。" : error.message);
    } finally { setBusy(false); }
    if (loaded) await checkFile();
  }

  async function initialize() {
    try {
      const response = await fetch("/api/meta", {cache: "no-store"});
      state.meta = await apiJSON(response);
      if (!state.meta.token) throw new Error("检查服务没有返回会话凭据，请刷新页面重试。");
      if (Array.isArray(state.meta.default_categories)) ui.categories.value = state.meta.default_categories.join(",");
      if (Array.isArray(state.meta.crs_options) && state.meta.crs_options.length) {
        ui.crs.replaceChildren();
        state.meta.crs_options.forEach((option) => {
          const value = typeof option === "object" ? option.value : option;
          const label = typeof option === "object" ? option.label || option.value : option;
          const element = node("option", label || "未声明");
          element.value = value ?? "";
          ui.crs.append(element);
        });
      }
      setText(ui.status, "本地检查服务已就绪");
      setText(el("version-label"), `· ${state.meta.version || "本地原型"}`);
    } catch (error) {
      state.meta = null;
      setText(ui.status, "本地服务未连接，请使用启动脚本打开工作台");
      notice(error instanceof TypeError ? "无法连接本地检查服务。请运行项目启动脚本，再通过启动窗口显示的本地地址打开本页。" : error.message);
    } finally { setBusy(false); }
  }

  ui.form.addEventListener("submit", (event) => { event.preventDefault(); checkFile(); });
  ui.file.addEventListener("change", () => selectFile(ui.file.files?.[0]));
  [ui.crs, ui.categories, ui.demo].forEach((control) => control.addEventListener("input", () => {
    clearResult();
    if (state.meta) setText(ui.status, "配置已更新，请重新检查");
  }));
  ui.normal.addEventListener("click", () => loadSample("normal"));
  ui.issues.addEventListener("click", () => loadSample("issues"));
  document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    state.visible = 100;
    document.querySelectorAll(".filter").forEach((item) => {
      item.classList.toggle("active", item === button);
      item.setAttribute("aria-pressed", String(item === button));
    });
    renderIssues();
  }));
  ui.more.addEventListener("click", () => { state.visible += 100; renderIssues(); });
  el("download-report").addEventListener("click", () => download(state.response?.report_html || "", "text/html;charset=utf-8", "检查报告.html"));
  el("download-issues").addEventListener("click", () => download(state.response?.issues_csv || "", "text/csv;charset=utf-8", "问题清单.csv"));
  initialize();
})();
