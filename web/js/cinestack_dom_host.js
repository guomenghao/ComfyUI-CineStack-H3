// Native connection events work with both LiteGraph and Nodes 2.0's WidgetDOM.
// The renderer may reparent the same element; this must not destroy the editor.
const HOST_TAG = "cinestack-director-host";
if (!customElements.get(HOST_TAG)) {
    customElements.define(HOST_TAG, class extends HTMLElement {
        connectedCallback() {
            queueMicrotask(() => {
                if (this.isConnected) this.onCineStackMount?.();
            });
        }
    });
}

export function createDirectorHost(onMount) {
    const host = document.createElement(HOST_TAG);
    host.className = "cstk-host";
    // Apply before editor CSS exists, including the initialization error path.
    host.style.cssText = "display:flex;flex-direction:column;width:100%;box-sizing:border-box;overflow:hidden";
    host.onCineStackMount = onMount;
    return host;
}

export function restoreDirectorRoot(container, root) {
    for (const extra of container.querySelectorAll(":scope > .bd-wrap, :scope > .cstk-mount-error")) {
        if (extra !== root) extra.remove();
    }
    if (root.parentElement !== container) container.appendChild(root);
}

export function showDirectorMountError(container, retry) {
    container.querySelector(":scope > .cstk-mount-error")?.remove();
    const panel = document.createElement("div");
    panel.className = "cstk-mount-error";
    panel.setAttribute("role", "alert");
    panel.style.cssText = "padding:20px;color:var(--input-text,#eee);background:var(--comfy-menu-bg,#252525);font:14px/1.6 sans-serif";
    const message = document.createElement("p");
    message.textContent = "导演台面板加载失败 / Director panel failed to load. 设置和缓存未被清除。请重试；若仍失败，请保存工作流并提供浏览器控制台中的 CineStack 错误。";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "重新加载面板 / Retry panel";
    button.style.cssText = "padding:8px 14px;cursor:pointer";
    button.onclick = retry;
    panel.append(message, button);
    container.appendChild(panel);
}
