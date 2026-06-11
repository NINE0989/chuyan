(function () {
  const STAGES = {
    analyze: {
      title: "正在分析音乐与需求",
      subtitle: "读取描述、音乐线索和视觉风格，准备生成方案。",
      label: "分析中",
    },
    build: {
      title: "正在生成 Shader 代码",
      subtitle: "组织 GLSL 结构、音频响应和画面运动逻辑。",
      label: "生成中",
    },
    ready: {
      title: "分析完成",
      subtitle: "确认后开始生成 Shader 代码。",
      label: "等待确认",
    },
    complete: {
      title: "Shader 已生成",
      subtitle: "正在刷新页面并重新加载代码块工具。",
      label: "完成",
    },
  };

  let overlay = null;

  function ensureOverlay() {
    if (overlay) return overlay;
    const preview = document.getElementById("preview-section");
    if (!preview) return null;

    overlay = document.createElement("div");
    overlay.className = "ms-ai-loading";
    overlay.hidden = true;
    overlay.setAttribute("role", "status");
    overlay.setAttribute("aria-live", "polite");
    overlay.innerHTML = `
      <div class="ms-ai-loading-panel">
        <div class="ms-ai-loader-scene" aria-hidden="true">
          <div class="ms-ai-orbit"></div>
          <div class="ms-ai-orbit is-wide"></div>
          <div class="ms-ai-core"></div>
          <div class="ms-ai-wave">
            <span></span><span></span><span></span><span></span>
            <span></span><span></span><span></span>
          </div>
        </div>
        <div>
          <div class="ms-ai-loading-title"></div>
          <div class="ms-ai-loading-subtitle"></div>
          <div class="ms-ai-loading-status">
            <span></span><span></span><span></span>
            <strong></strong>
          </div>
        </div>
      </div>
    `;
    preview.appendChild(overlay);
    return overlay;
  }

  function setCopy(stage) {
    const node = ensureOverlay();
    if (!node) return;
    const data = STAGES[stage] || STAGES.analyze;
    node.querySelector(".ms-ai-loading-title").textContent = data.title;
    node.querySelector(".ms-ai-loading-subtitle").textContent = data.subtitle;
    node.querySelector(".ms-ai-loading-status strong").textContent = data.label;
  }

  function show(stage) {
    const node = ensureOverlay();
    if (!node) return;
    node.dataset.stage = stage;
    setCopy(stage);
    node.hidden = false;
  }

  function update(stage) {
    if (!overlay || overlay.hidden) return;
    overlay.dataset.stage = stage;
    setCopy(stage);
  }

  function complete() {
    show("complete");
  }

  function hide() {
    if (overlay) overlay.hidden = true;
  }

  window.MusicShaderAILoading = { show, update, complete, hide };
})();
