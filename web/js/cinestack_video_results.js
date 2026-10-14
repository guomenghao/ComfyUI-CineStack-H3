/** Durable file delivery. Never fetch a whole video into a Blob/ArrayBuffer. */
import { api } from "../../scripts/api.js";
import { app } from "../../scripts/app.js";
import { getLocale, onLocaleChange } from "./minimax_i18n.js";

const text = (zh, en) => getLocale() === "zh" ? zh : en;
const PORTS = [["images", "IMAGE"], ["audio", "AUDIO"], ["fps", "FLOAT"], ["frame_count", "INT"],
    ["source_images", "IMAGE"], ["report", "STRING"], ["images_pre_refine", "IMAGE"],
    ["images_pre_face_refine", "IMAGE"], ["first_pass_video", "VIDEO"], ["final_video", "VIDEO"]];

export function ensureVideoOutputs(node) {
    if (!Array.isArray(node.outputs) || typeof node.addOutput !== "function") return;
    // Append only: existing output slots/links, including the old eight, stay put.
    while (node.outputs.length < PORTS.length) {
        const [name, type] = PORTS[node.outputs.length];
        node.addOutput(name, type);
    }
    for (const [index, label] of [[8, text("一采视频 · 文件", "First-pass video · file")],
                                  [9, text("最终视频 · 文件", "Final video · file")]]) {
        if (node.outputs[index]?.name === PORTS[index][0]) node.outputs[index].label = label;
    }
}

function videoUrl(row) {
    // Accept only a Comfy output locator, never a URL supplied by a saved workflow.
    if (row.type !== "output" || typeof row.filename !== "string" || /[\\/]/.test(row.filename)
        || !row.filename.endsWith(".mp4") || typeof row.subfolder !== "string"
        || row.subfolder.split(/[\\/]/).includes("..") || /^[\\/]/.test(row.subfolder)) return null;
    const query = new URLSearchParams({filename: row.filename, subfolder: row.subfolder, type: "output"});
    const path = `/view?${query}`;
    return api.apiURL ? api.apiURL(path) : path;
}

export const VIDEO_RESULT_STYLES = `
.cstk-overview .cs-videos{padding:12px;border-bottom:1px solid var(--cs-border)}
.cstk-overview .cs-videos h3{font-size:14px;line-height:1.5;margin:0 0 6px}
.cstk-overview .cs-videos p{margin:4px 0 8px;color:var(--cs-muted);overflow-wrap:anywhere}
.cstk-overview .cs-video-row{padding:10px 0;border-top:1px solid var(--cs-border);min-width:0}
.cstk-overview .cs-video-title{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.cstk-overview .cs-video-title small{color:var(--cs-muted)}
.cstk-overview .cs-video-actions{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.cstk-overview .cs-video-actions a{display:inline-flex;align-items:center;min-height:34px;padding:6px 10px;border:1px solid var(--cs-border);border-radius:6px;color:var(--cs-accent);text-decoration:underline;text-underline-offset:3px}
.cstk-overview .cs-video-actions a:hover{background:var(--cs-surface)}
.cstk-overview .cs-videos a:focus-visible{outline:2px solid var(--cs-accent);outline-offset:2px}
.cstk-overview .cs-video-row video{display:block;width:100%;max-height:300px;background:#000;margin-top:8px}
.cstk-overview .cs-video-path{overflow-wrap:anywhere;color:var(--cs-muted);user-select:text}
.cstk-overview .cs-video-path summary{padding:4px 0;text-decoration:underline;text-underline-offset:3px}
.cstk-overview .cs-video-error{color:var(--cs-error)!important}
`;

export class VideoResults {
    constructor(editor, parent) {
        this.editor = editor;
        this.root = document.createElement("section"); this.root.className = "cs-videos";
        this.root.setAttribute("aria-label", text("滚动视频结果", "Rolling video results"));
        parent.querySelector(".cs-list").before(this.root);
        this.rows = editor.node._cinestackVideoResults || app.nodeOutputs?.[editor.node.id]?.cinestack_videos || [];
        this.executed = ({detail}) => {
            if (String(detail?.display_node ?? detail?.node) !== String(editor.node.id)) return;
            if (Array.isArray(detail?.output?.cinestack_videos)) this.set(detail.output.cinestack_videos);
        };
        api.addEventListener("executed", this.executed);
        this.unsub = onLocaleChange(() => { ensureVideoOutputs(editor.node); this.render(); });
        this.render();
    }
    set(rows) {
        this.rows = Array.isArray(rows) ? rows : [];
        this.editor.node._cinestackVideoResults = this.rows;
        this.render();
    }
    releasePlayers() {
        for (const player of this.root.querySelectorAll("video")) {
            player.onerror = null; player.pause(); player.removeAttribute("src"); player.load();
        }
    }
    render() {
        this.releasePlayers(); this.root.replaceChildren();
        const title = document.createElement("h3"); title.textContent = text("滚动视频 · 最近完成结果", "Rolling videos · last completed results");
        const hint = document.createElement("p");
        hint.textContent = text("生成完成后在此预览或下载。另存到服务器：将右侧“一采视频 / 最终视频”直接连接 SaveVideo，格式和编码选择 auto。", "Preview or download completed files here. To save another server copy, connect First-pass / Final video directly to SaveVideo with format and codec set to auto.");
        this.root.append(title, hint);
        if (!this.rows.length) {
            const empty = document.createElement("p"); empty.textContent = text("尚无本轮滚动视频。普通模式仍使用原 IMAGE / AUDIO 接线。", "No rolling results yet. Normal mode continues to use IMAGE / AUDIO outputs."); this.root.append(empty);
        }
        for (const stage of ["first", "final"]) {
            const row = this.rows.find(item => item.stage === stage); if (!row) continue;
            const section = document.createElement("div"); section.className = "cs-video-row"; section.dataset.stage = stage;
            const heading = document.createElement("div"); heading.className = "cs-video-title";
            const name = document.createElement("strong"); name.textContent = stage === "first" ? text("一采视频", "First-pass video") : text("最终视频", "Final video");
            const scope = document.createElement("small"); scope.textContent = row.scope === "timeline" ? text("完整时间轴", "Full timeline") : text("本轮选中段", "Selected segments");
            if (row.available && !row.complete) scope.textContent += text(" · 仅部分段有此阶段", " · partial stage coverage");
            heading.append(name, scope); section.append(heading);
            const url = row.available ? videoUrl(row) : null;
            if (url) {
                const actions = document.createElement("div"); actions.className = "cs-video-actions";
                const preview = document.createElement("button"); preview.type = "button"; preview.textContent = text("预览视频", "Preview video"); preview.setAttribute("aria-expanded", "false");
                const download = document.createElement("a"); download.href = url; download.download = row.filename; download.textContent = text("下载到本机", "Download file");
                const player = document.createElement("video"); player.controls = true; player.preload = "none"; player.playsInline = true; player.hidden = true; player.style.display = "none";
                player.setAttribute("aria-label", name.textContent);
                const error = document.createElement("p"); error.className = "cs-video-error"; error.setAttribute("role", "status"); error.hidden = true;
                player.onerror = () => { if (player.hidden || !player.hasAttribute("src")) return; error.hidden = false; error.textContent = text("无法播放：请确认服务器文件仍存在。可尝试下载后播放，或检查 report 中的路径。", "Playback failed. Check that the server file still exists, try downloading it, or inspect the report path."); this.editor.updateDomWidgetHeight?.(); };
                preview.onclick = () => {
                    const open = player.hidden;
                    player.hidden = !open; player.style.display = open ? "block" : "none";
                    preview.textContent = open ? text("收起预览", "Close preview") : text("预览视频", "Preview video"); preview.setAttribute("aria-expanded", String(open));
                    if (open) { player.src = url; error.hidden = true; }
                    else { error.hidden = true; player.pause(); player.removeAttribute("src"); player.load(); }
                    this.editor.updateDomWidgetHeight?.();
                };
                actions.append(preview, download); section.append(actions, player, error);
                const path = document.createElement("details"); path.className = "cs-video-path";
                const summary = document.createElement("summary"); summary.textContent = text("服务器保存位置", "Server file location");
                const value = document.createElement("span"); value.textContent = row.path || `${row.subfolder}/${row.filename}`;
                path.append(summary, value); section.append(path);
            } else {
                const reason = document.createElement("p"); reason.textContent = row.reason || text("视频地址不可用，请查看 report。", "Video unavailable; check the report."); section.append(reason);
            }
            if (row.port_warning) { const warning = document.createElement("p"); warning.textContent = row.port_warning; section.append(warning); }
            this.root.append(section);
        }
        this.editor.updateDomWidgetHeight?.();
    }
    dispose() { this.releasePlayers(); this.unsub?.(); api.removeEventListener("executed", this.executed); this.root.remove(); }
}
