(function () {
  "use strict";

  const root = document.getElementById("advisor-copilot-root");
  if (!root || typeof SCRIPT_PREFIX === "undefined") {
    return;
  }

  const pill = document.getElementById("advisor-pill");
  const panel = document.getElementById("advisor-panel");
  const activeDot = document.getElementById("advisor-active-dot");
  const unreadDot = document.getElementById("advisor-unread-dot");
  const statusEl = document.getElementById("advisor-status");
  const closeButton = document.getElementById("advisor-close");
  const newChatButton = document.getElementById("advisor-new-chat");
  const fullscreenButton = document.getElementById("advisor-fullscreen-toggle");
  const tabButtons = Array.from(root.querySelectorAll("[data-advisor-tab]"));
  const chatPanel = document.getElementById("advisor-chat-panel");
  const memoryPanel = document.getElementById("advisor-memory-panel");
  const conversationSelect = document.getElementById("advisor-conversation-select");
  const errorEl = document.getElementById("advisor-error");
  const startersEl = document.getElementById("advisor-starters");
  const messagesEl = document.getElementById("advisor-messages");
  const form = document.getElementById("advisor-form");
  const input = document.getElementById("advisor-input");
  const sendButton = document.getElementById("advisor-send");
  const memoryEditButton = document.getElementById("advisor-memory-edit");
  const memoryForm = document.getElementById("advisor-memory-form");
  const memoryContentInput = document.getElementById("advisor-memory-content");
  const memorySaveButton = document.getElementById("advisor-memory-save");
  const memoryCancelButton = document.getElementById("advisor-memory-cancel");
  const memoryDocumentEl = document.getElementById("advisor-memory-document");

  const openStorageKey = "expenseAdvisorPanelOpen";
  const activeStatuses = new Set(["pending", "running"]);
  const terminalStatuses = new Set(["completed", "waiting_for_user", "failed", "canceled"]);
  const tabPanels = {
    chat: chatPanel,
    memory: memoryPanel,
  };

  const state = {
    activeConversationId: null,
    conversations: [],
    messages: [],
    memory: { content: "", updated_at: null },
    runs: new Map(),
    pollTimers: new Map(),
    activeTab: "chat",
    isEditingMemory: false,
    isFullscreen: false,
    isOpen: readOpenState(),
    unread: false,
    loading: false,
    memoryLoading: false,
    memoryRequestId: 0,
  };

  pill.addEventListener("click", () => setOpen(true));
  closeButton.addEventListener("click", () => setOpen(false));
  newChatButton.addEventListener("click", () => startNewChat());
  fullscreenButton.addEventListener("click", () => setFullscreen(!state.isFullscreen));
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.advisorTab || "chat"));
  });
  conversationSelect.addEventListener("change", () => selectConversation(conversationSelect.value));
  input.addEventListener("input", () => resizeChatInput());
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendContent(input.value);
  });
  memoryForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveMemoryFromForm();
  });
  memoryEditButton.addEventListener("click", () => startMemoryEdit());
  memoryCancelButton.addEventListener("click", () => resetMemoryForm());
  startersEl.querySelectorAll("[data-advisor-starter]").forEach((button) => {
    button.addEventListener("click", () => sendContent(button.dataset.advisorStarter || ""));
  });

  setActiveTab(state.activeTab);
  renderMemory();
  resizeChatInput();
  setOpen(state.isOpen, { persist: false });
  bootstrapAdvisor();

  function readOpenState() {
    try {
      return window.localStorage.getItem(openStorageKey) === "true";
    } catch {
      return false;
    }
  }

  function persistOpenState(isOpen) {
    try {
      window.localStorage.setItem(openStorageKey, isOpen ? "true" : "false");
    } catch {
      return;
    }
  }

  function setOpen(isOpen, options) {
    const shouldPersist = !options || options.persist !== false;
    state.isOpen = isOpen;
    panel.classList.toggle("d-none", !isOpen);
    pill.classList.toggle("d-none", isOpen);
    pill.setAttribute("aria-expanded", isOpen ? "true" : "false");
    if (isOpen && state.activeTab === "chat") {
      state.unread = false;
      window.setTimeout(() => input.focus(), 0);
    } else if (!isOpen) {
      setFullscreen(false);
    }
    if (shouldPersist) {
      persistOpenState(isOpen);
    }
    updateRunIndicators();
  }

  async function bootstrapAdvisor() {
    setLoading(true, "Loading");
    try {
      const payload = await advisorFetch("/api/advisor/bootstrap/");
      state.conversations = payload.recent_conversations || [];
      state.memory = payload.memory || { content: "", updated_at: null };
      const pendingRuns = payload.pending_runs || [];
      pendingRuns.forEach((run) => {
        state.runs.set(run.id, run);
        startPolling(run);
      });
      renderConversationOptions();
      renderMemory();
      if (payload.active_conversation) {
        await loadConversation(payload.active_conversation.id, { silent: true, scroll: true });
      } else {
        renderMessages(true);
      }
      setError("");
    } catch (error) {
      setError(error.message || "Advisor is unavailable.");
    } finally {
      setLoading(false);
      updateRunIndicators();
    }
  }

  async function selectConversation(value) {
    if (!value) {
      state.activeConversationId = null;
      state.messages = [];
      renderConversationOptions();
      renderMessages(true);
      return;
    }
    await loadConversation(Number(value), { scroll: true });
  }

  async function loadConversation(conversationId, options) {
    const silent = options && options.silent;
    const shouldScroll = options && options.scroll;
    if (!silent) {
      setLoading(true, "Loading conversation");
    }
    try {
      const payload = await advisorFetch(`/api/advisor/conversations/${conversationId}/`);
      state.activeConversationId = payload.conversation.id;
      state.messages = payload.messages || [];
      state.conversations = upsertConversation(state.conversations, payload.conversation);
      (payload.runs || []).forEach((run) => {
        state.runs.set(run.id, run);
        startPolling(run);
      });
      renderConversationOptions();
      renderMessages(shouldScroll || isNearMessageBottom());
      setError("");
    } catch (error) {
      setError(error.message || "Conversation could not be loaded.");
    } finally {
      if (!silent) {
        setLoading(false);
      }
      updateRunIndicators();
    }
  }

  async function startNewChat() {
    setLoading(true, "Creating conversation");
    try {
      const conversation = await createConversation("New conversation");
      state.activeConversationId = conversation.id;
      state.messages = [];
      renderConversationOptions();
      renderMessages(true);
      setOpen(true);
      setError("");
    } catch (error) {
      setError(error.message || "Conversation could not be created.");
    } finally {
      setLoading(false);
    }
  }

  async function sendContent(rawContent) {
    const content = rawContent.trim();
    if (!content) {
      return;
    }
    setOpen(true);
    setLoading(true, "Sending");
    try {
      let conversationId = state.activeConversationId;
      if (!conversationId) {
        const conversation = await createConversation(titleFromMessage(content));
        conversationId = conversation.id;
        state.activeConversationId = conversationId;
        state.messages = [];
      }
      const payload = await advisorFetch(`/api/advisor/conversations/${conversationId}/messages/`, {
        method: "POST",
        body: { content },
      });
      state.conversations = upsertConversation(state.conversations, payload.conversation);
      state.messages.push(payload.message);
      state.runs.set(payload.run.id, payload.run);
      startPolling(payload.run);
      input.value = "";
      resizeChatInput();
      renderConversationOptions();
      renderMessages(true);
      setError("");
    } catch (error) {
      setError(error.message || "Message could not be sent.");
    } finally {
      setLoading(false);
      updateRunIndicators();
    }
  }

  async function createConversation(title) {
    const payload = await advisorFetch("/api/advisor/conversations/", {
      method: "POST",
      body: { title },
    });
    state.conversations = upsertConversation(state.conversations, payload.conversation);
    return payload.conversation;
  }

  function setActiveTab(tab) {
    const activeTab = tab === "memory" ? "memory" : "chat";
    state.activeTab = activeTab;
    tabButtons.forEach((button) => {
      const isActive = button.dataset.advisorTab === activeTab;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    Object.keys(tabPanels).forEach((key) => {
      const item = tabPanels[key];
      if (item) {
        item.classList.toggle("d-none", key !== activeTab);
      }
    });
    if (activeTab === "memory") {
      renderMemory();
      refreshMemory();
    } else if (state.isOpen) {
      window.setTimeout(() => input.focus(), 0);
    }
  }

  function setFullscreen(isFullscreen) {
    state.isFullscreen = isFullscreen;
    root.classList.toggle("advisor-fullscreen", isFullscreen);
    fullscreenButton.title = isFullscreen ? "Exit fullscreen" : "Fullscreen";
    fullscreenButton.setAttribute("aria-label", isFullscreen ? "Exit fullscreen" : "Fullscreen");
    setButtonContent(fullscreenButton, isFullscreen ? "bi bi-fullscreen-exit" : "bi bi-arrows-fullscreen", "");
    resizeChatInput();
  }

  async function refreshMemory(options) {
    const silent = options && options.silent;
    state.memoryRequestId += 1;
    const requestId = state.memoryRequestId;
    if (!silent) {
      state.memoryLoading = true;
      renderMemory();
      setLoading(true, "Loading context");
    }
    try {
      const payload = await advisorFetch("/api/advisor/memory/");
      if (requestId !== state.memoryRequestId) {
        return;
      }
      state.memory = payload.memory || { content: "", updated_at: null };
      renderMemory();
      setError("");
    } catch (error) {
      if (!silent) {
        setError(error.message || "Context could not be loaded.");
      }
    } finally {
      if (!silent) {
        state.memoryLoading = false;
        renderMemory();
        setLoading(false);
      }
    }
  }

  async function saveMemoryFromForm() {
    const content = memoryContentInput.value.trim();
    setLoading(true, "Saving context");
    try {
      const payload = await advisorFetch("/api/advisor/memory/", {
        method: "POST",
        body: { content },
      });
      state.memory = payload.memory || { content: "", updated_at: null };
      resetMemoryForm();
      renderMemory();
      setError("");
    } catch (error) {
      setError(error.message || "Context could not be saved.");
    } finally {
      setLoading(false);
    }
  }

  function startMemoryEdit() {
    state.isEditingMemory = true;
    memoryContentInput.value = state.memory.content || "";
    memoryCancelButton.classList.remove("d-none");
    setButtonContent(memorySaveButton, "bi bi-save", "Save");
    renderMemory();
    memoryContentInput.focus();
  }

  function resetMemoryForm() {
    state.isEditingMemory = false;
    memoryForm.reset();
    memoryCancelButton.classList.add("d-none");
    setButtonContent(memorySaveButton, "bi bi-save", "Save");
    renderMemory();
  }

  function startPolling(run) {
    if (!run || !activeStatuses.has(run.status) || state.pollTimers.has(run.id)) {
      return;
    }
    const timer = window.setInterval(() => pollRun(run.id), 2500);
    state.pollTimers.set(run.id, timer);
    pollRun(run.id);
  }

  async function pollRun(runId) {
    const previousRun = state.runs.get(runId);
    try {
      const payload = await advisorFetch(`/api/advisor/runs/${runId}/`);
      const run = payload.run;
      const wasActive = previousRun && activeStatuses.has(previousRun.status);
      state.runs.set(run.id, run);
      if (state.activeConversationId === run.conversation_id) {
        renderMessages(isNearMessageBottom());
      }
      if (terminalStatuses.has(run.status)) {
        stopPolling(run.id);
        if (state.activeConversationId === run.conversation_id) {
          await loadConversation(run.conversation_id, { silent: true, scroll: isNearMessageBottom() });
        }
        await refreshMemory({ silent: true });
        if (wasActive && !state.isOpen && (run.final_markdown || run.error)) {
          state.unread = true;
        }
      }
      updateRunIndicators();
    } catch {
      updateRunIndicators();
    }
  }

  function stopPolling(runId) {
    const timer = state.pollTimers.get(runId);
    if (timer) {
      window.clearInterval(timer);
      state.pollTimers.delete(runId);
    }
  }

  async function advisorFetch(path, options) {
    const method = options && options.method ? options.method : "GET";
    const request = {
      method,
      cache: method === "GET" ? "no-store" : "default",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
      },
    };
    if (!["GET", "HEAD"].includes(method)) {
      request.headers["X-CSRFToken"] = getCsrfToken();
    }
    if (options && Object.prototype.hasOwnProperty.call(options, "body")) {
      request.headers["Content-Type"] = "application/json";
      request.body = JSON.stringify(options.body);
    }
    const response = await fetch(SCRIPT_PREFIX + path, request);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(errorMessageFromPayload(payload) || "Advisor request failed.");
    }
    return payload;
  }

  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function errorMessageFromPayload(payload) {
    if (payload && typeof payload.error === "string") {
      return payload.error;
    }
    if (!payload || !payload.errors || typeof payload.errors !== "object") {
      return "";
    }
    const messages = [];
    Object.keys(payload.errors).forEach((key) => {
      const value = payload.errors[key];
      if (Array.isArray(value)) {
        messages.push(...value);
      } else if (typeof value === "string") {
        messages.push(value);
      }
    });
    return messages.join(" ");
  }

  function renderMemory() {
    memoryDocumentEl.textContent = "";
    const content = state.memory.content || "";
    if (state.memoryLoading && !state.isEditingMemory) {
      memoryDocumentEl.appendChild(loadingSpinner("Loading memory"));
    } else if (content) {
      memoryDocumentEl.textContent = content;
    } else {
      appendEmptyState(memoryDocumentEl, "No saved memory yet.");
    }
    memoryDocumentEl.classList.toggle("d-none", state.isEditingMemory);
    memoryForm.classList.toggle("d-none", !state.isEditingMemory);
    memoryEditButton.classList.toggle("d-none", state.isEditingMemory);
  }

  function appendEmptyState(container, text) {
    const empty = document.createElement("div");
    empty.className = "advisor-empty";
    empty.textContent = text;
    container.appendChild(empty);
  }

  function actionButton(label, iconClass, buttonClass) {
    const button = document.createElement("button");
    button.className = `btn btn-sm ${buttonClass}`;
    button.type = "button";
    setButtonContent(button, iconClass, label);
    return button;
  }

  function setButtonContent(button, iconClass, label) {
    button.textContent = "";
    const icon = document.createElement("i");
    icon.className = iconClass;
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);
    if (label) {
      button.appendChild(document.createTextNode(` ${label}`));
    }
  }

  function renderConversationOptions() {
    conversationSelect.textContent = "";
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "New conversation";
    conversationSelect.appendChild(emptyOption);
    sortedConversations().forEach((conversation) => {
      const option = document.createElement("option");
      option.value = String(conversation.id);
      option.textContent = conversation.title || "Conversation";
      conversationSelect.appendChild(option);
    });
    conversationSelect.value = state.activeConversationId ? String(state.activeConversationId) : "";
  }

  function renderMessages(shouldScroll) {
    messagesEl.textContent = "";
    const messages = sortedMessages();
    const visibleRuns = runsForActiveConversation();
    const assistantRunIds = new Set(
      messages.filter((message) => message.role === "assistant" && message.linked_run_id).map((message) => message.linked_run_id),
    );
    const runsByMessageId = new Map(visibleRuns.map((run) => [run.user_message_id, run]));

    if (messages.length === 0 && visibleRuns.length === 0) {
      const empty = document.createElement("div");
      empty.className = "advisor-empty";
      empty.textContent = "Select one of the options below or ask a question.";
      messagesEl.appendChild(empty);
    }

    messages.forEach((message) => {
      renderMessage(message);
      if (message.role === "user") {
        const run = runsByMessageId.get(message.id);
        if (run && !assistantRunIds.has(run.id)) {
          renderRun(run);
        }
      }
    });

    startersEl.classList.toggle("d-none", messages.length > 0);
    if (shouldScroll) {
      scrollMessagesToBottom();
    }
  }

  function renderMessage(message) {
    if (message.role === "assistant") {
      renderAssistantBubble(message.content, message.created_at);
      return;
    }
    const bubble = document.createElement("div");
    bubble.className = "advisor-message advisor-message-user";
    const content = document.createElement("div");
    content.className = "advisor-message-content";
    content.textContent = message.content;
    bubble.appendChild(content);
    bubble.appendChild(messageTimeMeta(message.created_at));
    bubble.appendChild(userMessageActions(message.content));
    messagesEl.appendChild(bubble);
  }

  function renderRun(run) {
    if (run.final_markdown || run.error) {
      renderAssistantBubble(run.final_markdown || run.error, run.updated_at);
      return;
    }
    if (run.status === "failed") {
      renderAssistantBubble("AI Advisor could not complete the request.", run.updated_at);
      return;
    }
    if (run.status === "canceled") {
      renderAssistantBubble("Request canceled.", run.updated_at);
      return;
    }
    renderAssistantLoadingBubble(run.updated_at);
  }

  function renderAssistantBubble(markdown, timestamp) {
    const bubble = document.createElement("div");
    bubble.className = "advisor-message advisor-message-assistant";

    const meta = document.createElement("div");
    meta.className = "advisor-message-meta";
    const labelEl = document.createElement("span");
    labelEl.textContent = "AI Advisor";
    meta.appendChild(labelEl);
    meta.appendChild(messageTime(timestamp));

    const content = document.createElement("div");
    content.className = "advisor-message-content";
    renderSafeMarkdown(content, markdown);
    bubble.appendChild(meta);
    bubble.appendChild(content);
    if (markdown) {
      bubble.appendChild(assistantMessageActions(markdown));
    }
    messagesEl.appendChild(bubble);
  }

  function renderAssistantLoadingBubble(timestamp) {
    const bubble = document.createElement("div");
    bubble.className = "advisor-message advisor-message-assistant advisor-message-loading";

    const meta = document.createElement("div");
    meta.className = "advisor-message-meta";
    const labelEl = document.createElement("span");
    labelEl.textContent = "AI Advisor";
    meta.appendChild(labelEl);
    meta.appendChild(messageTime(timestamp));

    bubble.appendChild(meta);
    bubble.appendChild(loadingSpinner("Thinking"));
    messagesEl.appendChild(bubble);
  }

  function loadingSpinner(label) {
    const wrap = document.createElement("div");
    wrap.className = "advisor-loading";
    wrap.setAttribute("role", "status");
    wrap.setAttribute("aria-label", label);

    const spinner = document.createElement("span");
    spinner.className = "advisor-spinner";
    spinner.setAttribute("aria-hidden", "true");
    wrap.appendChild(spinner);
    return wrap;
  }

  function messageTimeMeta(timestamp) {
    const meta = document.createElement("div");
    meta.className = "advisor-message-meta advisor-message-meta-time";
    meta.appendChild(messageTime(timestamp));
    return meta;
  }

  function messageTime(timestamp) {
    const time = document.createElement("time");
    time.className = "advisor-message-time";
    time.dateTime = timestamp || "";
    time.textContent = formatMessageTime(timestamp);
    return time;
  }

  function userMessageActions(messageContent) {
    const actions = document.createElement("div");
    actions.className = "advisor-message-actions";
    const copyButton = messageActionButton("Copy your message", "bi bi-copy", "");
    copyButton.addEventListener("click", () => copyToClipboard(messageContent, copyButton, "Copied"));
    const editButton = messageActionButton("Edit and resend", "bi bi-pencil-square", "Edit");
    editButton.addEventListener("click", () => startMessageEdit(messageContent));
    actions.append(copyButton, editButton);
    return actions;
  }

  function assistantMessageActions(markdown) {
    const actions = document.createElement("div");
    actions.className = "advisor-message-actions";
    const copyButton = messageActionButton("Copy full answer", "bi bi-copy", "");
    copyButton.addEventListener("click", () => copyToClipboard(markdown, copyButton, "Copied"));
    actions.appendChild(copyButton);
    return actions;
  }

  function renderSafeMarkdown(container, markdown) {
    container.textContent = "";
    const fragment = document.createDocumentFragment();
    const lines = String(markdown || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
    let index = 0;

    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) {
        index += 1;
      } else if (line.startsWith("```")) {
        index = appendCodeBlock(fragment, lines, index);
      } else if (isHorizontalRule(line)) {
        appendHorizontalRule(fragment);
        index += 1;
      } else if (/^#{1,3}\s+\S/.test(line)) {
        appendHeading(fragment, line);
        index += 1;
      } else if (isTableStart(lines, index)) {
        index = appendTable(fragment, lines, index);
      } else if (/^\s*>\s?/.test(line)) {
        index = appendBlockquote(fragment, lines, index);
      } else if (/^\s*[-*]\s+\S/.test(line)) {
        index = appendList(fragment, lines, index, false);
      } else if (/^\s*\d+\.\s+\S/.test(line)) {
        index = appendList(fragment, lines, index, true);
      } else {
        index = appendParagraph(fragment, lines, index);
      }
    }

    container.appendChild(fragment);
  }

  function appendCodeBlock(fragment, lines, startIndex) {
    const codeLines = [];
    let index = startIndex + 1;
    while (index < lines.length && !lines[index].startsWith("```")) {
      codeLines.push(lines[index]);
      index += 1;
    }
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = codeLines.join("\n");
    pre.appendChild(code);
    fragment.appendChild(pre);
    return index < lines.length ? index + 1 : index;
  }

  function appendHorizontalRule(fragment) {
    fragment.appendChild(document.createElement("hr"));
  }

  function appendHeading(fragment, line) {
    const match = line.match(/^(#{1,3})\s+(.+)$/);
    const level = match ? match[1].length : 3;
    const heading = document.createElement(`h${level}`);
    appendInline(heading, match ? match[2].trim() : line.trim());
    fragment.appendChild(heading);
  }

  function appendList(fragment, lines, startIndex, isOrdered) {
    const list = document.createElement(isOrdered ? "ol" : "ul");
    const pattern = isOrdered ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*]\s+(.+)$/;
    let index = startIndex;
    while (index < lines.length) {
      const match = lines[index].match(pattern);
      if (!match) {
        break;
      }
      const item = document.createElement("li");
      appendInline(item, match[1].trim());
      list.appendChild(item);
      index += 1;
    }
    fragment.appendChild(list);
    return index;
  }

  function appendBlockquote(fragment, lines, startIndex) {
    const quote = document.createElement("blockquote");
    const parts = [];
    let index = startIndex;
    while (index < lines.length) {
      const match = lines[index].match(/^\s*>\s?(.*)$/);
      if (!match) {
        break;
      }
      const text = match[1].trim();
      if (text) {
        parts.push(text);
      } else {
        appendBlockquoteParagraph(quote, parts);
      }
      index += 1;
    }
    appendBlockquoteParagraph(quote, parts);
    fragment.appendChild(quote);
    return index;
  }

  function appendBlockquoteParagraph(quote, parts) {
    if (parts.length === 0) {
      return;
    }
    const paragraph = document.createElement("p");
    appendInline(paragraph, parts.join(" "));
    quote.appendChild(paragraph);
    parts.length = 0;
  }

  function appendParagraph(fragment, lines, startIndex) {
    const parts = [];
    let index = startIndex;
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines, index)) {
      parts.push(lines[index].trim());
      index += 1;
    }
    const paragraph = document.createElement("p");
    appendInline(paragraph, parts.join(" "));
    fragment.appendChild(paragraph);
    return index;
  }

  function appendTable(fragment, lines, startIndex) {
    const headerCells = splitTableRow(lines[startIndex]);
    const alignments = splitTableRow(lines[startIndex + 1]).map(tableAlignment);
    const wrapper = document.createElement("div");
    wrapper.className = "advisor-table-wrap";
    const table = document.createElement("table");
    table.className = "advisor-markdown-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerCells.forEach((cell, cellIndex) => {
      const heading = document.createElement("th");
      applyTableAlignment(heading, alignments[cellIndex]);
      appendInline(heading, cell);
      headerRow.appendChild(heading);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    let index = startIndex + 2;
    while (index < lines.length && isTableRow(lines[index]) && !isTableDivider(lines[index])) {
      const row = document.createElement("tr");
      splitTableRow(lines[index]).forEach((cell, cellIndex) => {
        const data = document.createElement("td");
        applyTableAlignment(data, alignments[cellIndex]);
        appendInline(data, cell);
        row.appendChild(data);
      });
      tbody.appendChild(row);
      index += 1;
    }
    table.appendChild(tbody);
    wrapper.appendChild(table);
    fragment.appendChild(wrapper);
    return index;
  }

  function isBlockStart(lines, index) {
    const line = lines[index];
    return (
      line.startsWith("```") ||
      isHorizontalRule(line) ||
      /^#{1,3}\s+\S/.test(line) ||
      isTableStart(lines, index) ||
      /^\s*>\s?/.test(line) ||
      /^\s*[-*]\s+\S/.test(line) ||
      /^\s*\d+\.\s+\S/.test(line)
    );
  }

  function isHorizontalRule(line) {
    return /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line);
  }

  function isTableStart(lines, index) {
    return index + 1 < lines.length && isTableRow(lines[index]) && isTableDivider(lines[index + 1]);
  }

  function isTableRow(line) {
    return splitTableRow(line).length >= 2;
  }

  function splitTableRow(line) {
    const trimmed = line.trim();
    if (!trimmed.includes("|")) {
      return [];
    }
    return trimmed.replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
  }

  function isTableDivider(line) {
    const cells = splitTableRow(line);
    return cells.length >= 2 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, "")));
  }

  function tableAlignment(cell) {
    const compact = cell.replace(/\s+/g, "");
    if (compact.startsWith(":") && compact.endsWith(":")) {
      return "center";
    }
    if (compact.endsWith(":")) {
      return "right";
    }
    return "left";
  }

  function applyTableAlignment(cell, alignment) {
    if (alignment && alignment !== "left") {
      cell.style.textAlign = alignment;
    }
  }

  function appendInline(parent, text) {
    const tokenPattern = /(`[^`]+`|\*\*[^*]+?\*\*|\*[^*]+?\*|\[([^\]]+)\]\(([^)\s]+)\))/g;
    let lastIndex = 0;
    let match = tokenPattern.exec(text);
    while (match) {
      appendText(parent, text.slice(lastIndex, match.index));
      appendInlineToken(parent, match);
      lastIndex = match.index + match[0].length;
      match = tokenPattern.exec(text);
    }
    appendText(parent, text.slice(lastIndex));
  }

  function appendInlineToken(parent, match) {
    const token = match[0];
    if (token.startsWith("`")) {
      const code = document.createElement("code");
      code.textContent = token.slice(1, -1);
      parent.appendChild(code);
    } else if (token.startsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      parent.appendChild(strong);
    } else if (token.startsWith("*")) {
      const emphasis = document.createElement("em");
      emphasis.textContent = token.slice(1, -1);
      parent.appendChild(emphasis);
    } else if (match[2] && match[3]) {
      appendLink(parent, match[2], match[3]);
    }
  }

  function appendLink(parent, label, href) {
    const safeHref = safeUrl(href);
    if (!safeHref) {
      appendText(parent, label);
      return;
    }
    const link = document.createElement("a");
    link.href = safeHref;
    link.rel = "noopener noreferrer";
    link.target = "_blank";
    link.textContent = label;
    parent.appendChild(link);
  }

  function appendText(parent, text) {
    if (text) {
      parent.appendChild(document.createTextNode(text));
    }
  }

  function safeUrl(href) {
    try {
      const parsed = new URL(href, window.location.origin);
      if (["http:", "https:", "mailto:"].includes(parsed.protocol)) {
        return parsed.href;
      }
    } catch {
      return "";
    }
    return "";
  }

  function messageActionButton(title, iconClass, text) {
    const button = document.createElement("button");
    button.className = "advisor-message-action-btn";
    button.type = "button";
    button.title = title;
    button.setAttribute("aria-label", title);
    const icon = document.createElement("i");
    icon.className = iconClass;
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);
    button.appendChild(document.createTextNode(` ${text}`));
    return button;
  }

  function startMessageEdit(messageContent) {
    setActiveTab("chat");
    setOpen(true);
    input.value = messageContent;
    resizeChatInput();
    window.setTimeout(() => {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }, 0);
  }

  async function copyToClipboard(text, button, successText) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        fallbackCopy(text);
      }
      flashButton(button, successText);
    } catch {
      flashButton(button, "Copy failed");
    }
  }

  function fallbackCopy(text) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "readonly");
    textarea.style.position = "fixed";
    textarea.style.top = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }

  function flashButton(button, text) {
    const originalNodes = Array.from(button.childNodes).map((node) => node.cloneNode(true));
    button.textContent = text;
    window.setTimeout(() => {
      button.replaceChildren(...originalNodes.map((node) => node.cloneNode(true)));
    }, 1200);
  }

  function runsForActiveConversation() {
    if (!state.activeConversationId) {
      return [];
    }
    return Array.from(state.runs.values())
      .filter((run) => run.conversation_id === state.activeConversationId)
      .sort((first, second) => new Date(first.created_at) - new Date(second.created_at));
  }

  function sortedMessages() {
    return [...state.messages].sort((first, second) => new Date(first.created_at) - new Date(second.created_at));
  }

  function sortedConversations() {
    return [...state.conversations].sort((first, second) => new Date(second.updated_at) - new Date(first.updated_at));
  }

  function upsertConversation(conversations, conversation) {
    const filtered = conversations.filter((item) => item.id !== conversation.id);
    filtered.push(conversation);
    return filtered;
  }

  function titleFromMessage(content) {
    return content.length > 80 ? `${content.slice(0, 77)}...` : content;
  }

  function formatMessageTime(timestamp) {
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  function setLoading(isLoading, status) {
    state.loading = isLoading;
    input.disabled = isLoading;
    sendButton.disabled = isLoading;
    memoryEditButton.disabled = isLoading;
    memorySaveButton.disabled = isLoading;
    memoryCancelButton.disabled = isLoading;
    if (status) {
      statusEl.textContent = status;
    } else if (!hasActiveRun()) {
      statusEl.textContent = "Ready";
    }
  }

  function setError(message) {
    errorEl.textContent = message;
    errorEl.classList.toggle("d-none", !message);
  }

  function resizeChatInput() {
    const maxHeight = state.isFullscreen ? 256 : 176;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, maxHeight)}px`;
    sendButton.style.height = `${input.offsetHeight}px`;
  }

  function hasActiveRun() {
    return Array.from(state.runs.values()).some((run) => activeStatuses.has(run.status));
  }

  function updateRunIndicators() {
    const isActive = hasActiveRun();
    activeDot.classList.toggle("d-none", !isActive);
    unreadDot.classList.toggle("d-none", !state.unread);
    if (!state.loading) {
      statusEl.textContent = isActive ? "Running" : "Ready";
    }
  }

  function isNearMessageBottom() {
    return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 80;
  }

  function scrollMessagesToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
})();
