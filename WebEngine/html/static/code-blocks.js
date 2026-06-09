(function () {
  let defaultBlock = null;
  const listeners = new Set();
  let enhanced = false;
  let activeSessionId = "";

  function getSessionId() {
    if (typeof window.getCurrentMusicShaderSessionId === "function") {
      return window.getCurrentMusicShaderSessionId() || "__no_session__";
    }
    return activeSessionId || "__no_session__";
  }

  function storageKey(sessionId) {
    return `musicshader.defaultCodeBlock.${sessionId || "__no_session__"}`;
  }

  function hashText(text) {
    let hash = 2166136261;
    for (let i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
    }
    return (hash >>> 0).toString(16);
  }

  function notifyDefaultChange() {
    listeners.forEach((listener) => listener(defaultBlock));
  }

  function syncDefaultState() {
    document.querySelectorAll(".code-card, .ms-code-card").forEach((card) => {
      const id = card.dataset.codeBlockId || card.dataset.msCodeId;
      const isDefault = Boolean(defaultBlock && defaultBlock.id === id);
      card.classList.toggle("is-default", isDefault);
      card.classList.toggle("ms-default", isDefault);
      const button = card.querySelector("[data-action='default'], [data-ms-action='default']");
      if (button) {
        button.textContent = isDefault ? "已默认" : "设为默认";
        button.classList.toggle("is-active", isDefault);
        button.classList.toggle("ms-active", isDefault);
      }
    });
    const summary = document.getElementById("ms-default-summary");
    if (summary) {
      const sessionText = getSessionId() === "__no_session__" ? "当前会话" : "本会话";
      summary.textContent = defaultBlock ? `${sessionText}默认：${defaultBlock.title}` : `${sessionText}未选择默认代码`;
    }
  }

  function createButton(text, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.dataset.action = action;
    return button;
  }

  async function copyCode(button, code) {
    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(code);
      button.textContent = "已复制";
    } catch (error) {
      const fallback = document.createElement("textarea");
      fallback.value = code;
      fallback.style.position = "fixed";
      fallback.style.left = "-9999px";
      document.body.appendChild(fallback);
      fallback.select();
      document.execCommand("copy");
      fallback.remove();
      button.textContent = "已复制";
    }
    window.setTimeout(() => {
      button.textContent = original;
    }, 1200);
  }

  function codeFromPre(pre) {
    return pre.innerText.replace(/\n+$/g, "");
  }

  function setDefaultBlock(block) {
    defaultBlock = {
      ...block,
      sessionId: getSessionId(),
      selectedAt: new Date().toISOString(),
    };
    try {
      localStorage.setItem(storageKey(defaultBlock.sessionId), JSON.stringify(defaultBlock));
    } catch (error) {}
    syncDefaultState();
    notifyDefaultChange();
    if (typeof window.setStatus === "function") window.setStatus("已设为本会话默认代码");
  }

  function loadDefaultIntoEditor() {
    if (!defaultBlock) return;
    const editor = document.getElementById("code-editor");
    if (!editor) return;
    editor.value = defaultBlock.code;
    if (typeof window.currentCode !== "undefined") window.currentCode = defaultBlock.code;
    if (typeof window.setStatus === "function") window.setStatus("已加载默认代码到编辑器");
  }

  function enhancePre(pre, index) {
    if (pre.dataset.msEnhanced === "1") return;
    const code = codeFromPre(pre);
    if (!code.trim()) return;

    pre.dataset.msEnhanced = "1";
    const id = `session-${getSessionId()}-code-${hashText(code)}`;

    const card = document.createElement("div");
    card.className = "ms-code-card ms-collapsed";
    card.dataset.msCodeId = id;
    card.title = "点击代码块可设为本会话默认代码";

    const toolbar = document.createElement("div");
    toolbar.className = "ms-code-toolbar";

    const title = document.createElement("div");
    title.className = "ms-code-title";
    title.textContent = code.includes("void main") || code.includes("#version") ? "GLSL 代码块" : "代码块";

    const actions = document.createElement("div");
    actions.className = "ms-code-actions";

    const toggleButton = createButton("展开", "toggle");
    const copyButton = createButton("复制", "copy");
    const defaultButton = createButton("设为本会话默认", "default");
    const loadButton = createButton("加载", "load");

    toggleButton.dataset.msAction = "toggle";
    copyButton.dataset.msAction = "copy";
    defaultButton.dataset.msAction = "default";
    loadButton.dataset.msAction = "load";

    toggleButton.addEventListener("click", () => {
      const collapsed = card.classList.toggle("ms-collapsed");
      toggleButton.textContent = collapsed ? "展开" : "收起";
    });
    copyButton.addEventListener("click", () => copyCode(copyButton, codeFromPre(pre)));
    defaultButton.addEventListener("click", () => {
      setDefaultBlock({
        id,
        title: title.textContent,
        language: "glsl",
        code: codeFromPre(pre),
      });
    });
    card.addEventListener("click", (event) => {
      if (event.target.closest("button") || event.target.closest("pre")) return;
      setDefaultBlock({
        id,
        title: title.textContent,
        language: "glsl",
        code: codeFromPre(pre),
      });
    });
    pre.addEventListener("click", () => {
      if (!card.classList.contains("ms-collapsed")) return;
      card.classList.remove("ms-collapsed");
      toggleButton.textContent = "收起";
    });
    loadButton.addEventListener("click", () => {
      const editor = document.getElementById("code-editor");
      if (editor) {
        editor.value = codeFromPre(pre);
        if (typeof window.currentCode !== "undefined") window.currentCode = editor.value;
        if (typeof window.setStatus === "function") window.setStatus("已加载代码块到编辑器");
      }
    });

    actions.append(toggleButton, copyButton, defaultButton, loadButton);
    toolbar.append(title, actions);

    const parent = pre.parentNode;
    parent.insertBefore(card, pre);
    card.append(toolbar, pre);
    syncDefaultState();
  }

  function enhanceMessageCodeBlocks(root) {
    const scope = root || document;
    scope.querySelectorAll(".msg .bubble pre:not([data-ms-enhanced])").forEach(enhancePre);
    scope.querySelectorAll(".msg.ai .bubble:not([data-ms-plain-enhanced]), .msg.assistant .bubble:not([data-ms-plain-enhanced])").forEach(enhancePlainShaderBubble);
  }

  function looksLikeShader(text) {
    const value = text.trim();
    if (value.length < 120) return false;
    return (
      value.includes("#version") ||
      /void\s+mainImage\s*\(/.test(value) ||
      /void\s+main\s*\(/.test(value) ||
      (value.includes("uniform vec") && value.includes("fragColor"))
    );
  }

  function enhancePlainShaderBubble(bubble) {
    if (bubble.dataset.msPlainEnhanced === "1") return;
    if (bubble.querySelector("pre, .ms-code-card")) return;

    const text = bubble.innerText || "";
    if (!looksLikeShader(text)) return;

    bubble.dataset.msPlainEnhanced = "1";
    const codeText = text.trim();
    bubble.innerHTML = "";

    const pre = document.createElement("pre");
    pre.textContent = codeText;
    bubble.appendChild(pre);
    enhancePre(pre, 0);
  }

  function installEditorActions() {
    const header = document.getElementById("editor-header");
    const editor = document.getElementById("code-editor");
    if (!header || !editor || document.getElementById("ms-editor-actions")) return;

    const actions = document.createElement("div");
    actions.className = "ms-editor-actions";
    actions.id = "ms-editor-actions";

    const copyButton = createButton("复制当前代码", "editor-copy");
    const loadDefaultButton = createButton("加载默认", "editor-load-default");
    const clearDefaultButton = createButton("清除默认", "editor-clear-default");
    const summary = document.createElement("span");
    summary.className = "ms-default-summary";
    summary.id = "ms-default-summary";
    summary.textContent = "未选择默认代码";

    copyButton.addEventListener("click", () => copyCode(copyButton, editor.value));
    loadDefaultButton.addEventListener("click", loadDefaultIntoEditor);
    clearDefaultButton.addEventListener("click", clearDefault);

    actions.append(copyButton, loadDefaultButton, clearDefaultButton);
    header.append(summary, actions);
  }

  function installObserver() {
    const chat = document.getElementById("chat-messages");
    if (!chat) return;
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) enhanceMessageCodeBlocks(node);
        });
      });
      enhanceMessageCodeBlocks(chat);
    });
    observer.observe(chat, { childList: true, subtree: true });
    enhanceMessageCodeBlocks(chat);
  }

  function restoreDefault(options = {}) {
    activeSessionId = getSessionId();
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey(activeSessionId)) || "null");
      if (saved && saved.code) defaultBlock = saved;
      else defaultBlock = null;
    } catch (error) {}
    syncDefaultState();
    notifyDefaultChange();
    if (options.loadIntoEditor && defaultBlock) loadDefaultIntoEditor();
  }

  function init() {
    if (enhanced) return;
    enhanced = true;
    restoreDefault();
    installEditorActions();
    installObserver();
    syncDefaultState();
  }

  function renderCodeBlock(block) {
    const card = document.createElement("article");
    card.className = "code-card is-collapsed";
    card.dataset.codeBlockId = block.id;

    const toolbar = document.createElement("div");
    toolbar.className = "code-toolbar";

    const title = document.createElement("div");
    title.className = "code-title";
    title.textContent = `${block.title || block.id} · ${block.language || "text"}`;

    const actions = document.createElement("div");
    actions.className = "code-actions";

    const toggleButton = createButton("展开", "toggle");
    const copyButton = createButton("复制", "copy");
    const defaultButton = createButton("设为默认", "default");

    toggleButton.addEventListener("click", () => {
      const collapsed = card.classList.toggle("is-collapsed");
      toggleButton.textContent = collapsed ? "展开" : "折叠";
    });

    copyButton.addEventListener("click", () => copyCode(copyButton, block.code));

    defaultButton.addEventListener("click", () => {
      defaultBlock = {
        id: block.id,
        title: block.title || block.id,
        language: block.language || "text",
        code: block.code,
      };
      syncDefaultState();
      notifyDefaultChange();
    });

    actions.append(toggleButton, copyButton, defaultButton);
    toolbar.append(title, actions);

    const pre = document.createElement("pre");
    pre.className = "code-content";
    const code = document.createElement("code");
    code.textContent = block.code;
    pre.appendChild(code);

    card.append(toolbar, pre);
    return card;
  }

  function renderMessage(container, message) {
    const node = document.createElement("article");
    node.className = `message ${message.role || "ai"}`;

    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = message.role === "user" ? "你" : "AI";

    const text = document.createElement("div");
    text.className = "message-text";
    text.textContent = message.text || "";

    node.append(label, text);
    (message.codeBlocks || []).forEach((block) => {
      node.appendChild(renderCodeBlock(block));
    });

    container.appendChild(node);
    container.scrollTop = container.scrollHeight;
    syncDefaultState();
  }

  function clearDefault() {
    try {
      localStorage.removeItem(storageKey(getSessionId()));
    } catch (error) {}
    defaultBlock = null;
    syncDefaultState();
    notifyDefaultChange();
    if (typeof window.setStatus === "function") window.setStatus("已清除本会话默认代码");
  }

  function onDefaultChange(listener) {
    listeners.add(listener);
    listener(defaultBlock);
  }

  window.CodeBlocks = {
    renderMessage,
    clearDefault,
    onDefaultChange,
  };
  window.MusicShaderCodeEnhancer = {
    init,
    clearDefault,
    onDefaultChange,
    refresh(root) {
      enhanceMessageCodeBlocks(root || document);
      syncDefaultState();
    },
    onSessionChange(sessionId, options = {}) {
      activeSessionId = sessionId || "__no_session__";
      restoreDefault(options);
      window.setTimeout(() => syncDefaultState(), 0);
    },
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
