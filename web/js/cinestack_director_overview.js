/** Director workbench: derived UI only; workflow values stay in timeline_data. */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { getLocale, onLocaleChange } from "./minimax_i18n.js";
import { createSegmentSeedControl, normalizeSegmentSeed, syncSegmentSeedControls } from "./minimax_segment_seed.js";
import { syncFl2vFromShots } from "./minimax_fl2v.js";
import { cacheStatusPayload, diffLabel, connectedRefineForDirector } from "./minimax_refine.js";

const COPY = {
    zh: {
        conflict: "尚未提交：滚动生成＋全部导出需要统一输出阶段。当前工作流按缓存自动选择一采或二采，请先选择本轮阶段。",
        chooseFirst: "改为仅一采", chooseSecond: "改为仅二采", inspect: "查看问题段", retry: "重新检查缓存",
        actionNote: "这里只修改设置，不会自动开始生成；确认后点击“检查并运行”或顶部“运行”。",
        runSummary: "本轮：{n} 段 · {memory} · {export}", rollingName: "滚动生成", diskName: "低内存落盘", normalName: "常规生成",
        allExport: "全部导出", segmentExport: "分段导出", blockedTitle: "请先处理导演台设置",
        title: "分段工作台", count: "段", scope: "运行范围", all: "全部", selected: "勾选段", edit: "编辑",
        stage: "执行方式", legacy: "跟随工作流", first_pass: "仅一采", refine_only: "仅二采",
        refresh: "检查缓存", queue: "检查并运行", queued: "已提交队列", submitting: "正在提交…",
        seed: "一采 seed", inherit: "留空继承全局", fixed: "本段固定", global: "继承全局", pin: "固定当前值",
        unknown: "待检查", checking: "正在检查…", matched: "一采元数据匹配", missing: "缺少一采缓存",
        mismatch: "一采失配", damaged: "缓存异常", final: "成片缓存存在", noFinal: "暂无成片缓存",
        changed: "参数已变，请重新检查", failed: "缓存检查失败", empty: "添加片段后可在这里统一管理 seed 和缓存。",
        details: "查看差异", previous: "缓存", current: "当前", segment: "片段", linked: "seed 由外部接线控制",
        legacyHint: "沿用工作流中的 Refine / 脸修设置。", firstHint: "生成选中段的一采并保存缓存，跳过二采和脸修；全部导出时合并一采视频。",
        refineHint: "只读取匹配的一采缓存；运行前还会校验 latent，失配绝不补跑一采。",
        noRefine: "请连接并启用影栈 Refine（refine / upscale），并连接二采 SIGMAS。",
        noSelection: "请至少勾选一段。", noQueue: "请使用 ComfyUI 的队列按钮提交。",
        ready: "缓存元数据匹配；执行前仍需完整校验。", stale: "请先检查选中段缓存。",
        scopeHint: "通过当前工作流提交；未勾选段不重采。", invalidSeed: "请修正无效的一采 seed。",
        running: "正在执行", collapse: "收起或展开分段总览", unsupported: "此接线不能在工作台识别，请使用原接线模式。",
        blocked: "选中段缓存未匹配，请查看对应段差异，或改为仅一采重做该段。", skipped: "Refine 设置跳过了选中段，请检查 skip_fl2v。",
        pinUnsafe: "全局 seed 超出浏览器精确整数范围；请直接输入本段十进制 seed。",
        notConfirmed: "ComfyUI 尚未确认提交，请查看宿主队列或错误提示后再操作。",
        rolling: "滚动生成：保留当前段＋上一段；连续编码，无逐段/中间轮次视频；IMAGE/AUDIO 不输出，文件路径见报告。",
        rollingAll: "全部导出＋滚动：只生成选中段，复用其他段已有视频合成整片；缺失或失配会停止，不补跑。IMAGE/AUDIO 不输出，文件路径见报告。",
        lowMemory: "低内存落盘：只保存本轮勾选段，文件路径见报告；IMAGE/AUDIO 不输出完整视频。",
    },
    en: {
        conflict: "Not submitted: rolling generation with All export needs one output stage. The workflow currently chooses a stage per cache. Select first pass or second pass for this run.",
        chooseFirst: "Use first pass only", chooseSecond: "Use second pass only", inspect: "Show problem segments", retry: "Recheck cache",
        actionNote: "These actions change settings only. Review them, then choose Check and run or the main Run button.",
        runSummary: "This run: {n} segments · {memory} · {export}", rollingName: "Rolling", diskName: "Low RAM", normalName: "Standard",
        allExport: "All export", segmentExport: "Segment export", blockedTitle: "Review Director settings",
        title: "Segment workbench", count: "segments", scope: "Run scope", all: "All", selected: "Checked", edit: "Edit",
        stage: "Execution", legacy: "Follow graph", first_pass: "First pass only", refine_only: "Second pass only",
        refresh: "Check cache", queue: "Check and run", queued: "Queued", submitting: "Submitting…",
        seed: "First-pass seed", inherit: "Inherit global", fixed: "Fixed", global: "Global", pin: "Fix current value",
        unknown: "Not checked", checking: "Checking…", matched: "First-pass metadata match", missing: "First-pass cache missing",
        mismatch: "First-pass mismatch", damaged: "Cache error", final: "Rendered cache exists", noFinal: "No rendered cache",
        changed: "Settings changed; recheck", failed: "Cache check failed", empty: "Add segments to manage seeds and caches here.",
        details: "Differences", previous: "Cached", current: "Current", segment: "Segment", linked: "Seed controlled by a wired input",
        legacyHint: "Keep the graph's Refine and face-refinement behavior.", firstHint: "Regenerate checked first passes, save cache, skip refinement and face refinement.",
        refineHint: "Use matching first-pass cache only. Latents are validated before execution; never regenerate first passes.",
        noRefine: "Connect an enabled CineStack Refine (refine / upscale) and second-pass SIGMAS.",
        noSelection: "Check at least one segment.", noQueue: "Use the ComfyUI queue button to submit.",
        ready: "Metadata matches; full validation still runs before execution.", stale: "Check selected first-pass caches first.",
        scopeHint: "Submit the current workflow; unchecked segments are not resampled.", invalidSeed: "Correct invalid first-pass seeds.",
        running: "Running", collapse: "Expand or collapse the segment overview", unsupported: "This connection is not recognized here; use Follow graph.",
        blocked: "Selected caches do not match. Inspect segment differences or regenerate with First pass only.", skipped: "Refine skips a selected segment; check skip_fl2v.",
        pinUnsafe: "Global seed exceeds browser integer precision. Enter an exact decimal seed for this segment.",
        notConfirmed: "ComfyUI did not confirm submission. Check its queue or error message before retrying.",
        rolling: "Rolling: current + previous; continuous encoding without per-segment/intermediate videos. IMAGE/AUDIO blocked; see report paths.",
        rollingAll: "All + rolling: generate checked segments, reuse saved videos for the rest and export the full timeline. Missing/mismatched results stop the run; never resample unchecked segments. File output only.",
        lowMemory: "Low RAM: save checked segments only. See file paths in the report; IMAGE/AUDIO sockets do not emit full clips.",
    },
};
const label = (key) => COPY[getLocale() === "en" ? "en" : "zh"][key] || key;
const widget = (node, name) => node?.widgets?.find((w) => w.name === name);
const widgetValue = (node, name) => {
    const value = widget(node, name)?.value;
    return value && typeof value === "object" && "value" in value ? value.value : value;
};

export function overviewRows(editor) {
    return editor.isFl2vMode?.() ? (editor.timeline.shots || []) : (editor.timeline.segments || []);
}

export function effectiveSegmentSeed(row, node) {
    const fixed = normalizeSegmentSeed(row?.first_pass_seed);
    return { value: fixed ?? String(widgetValue(node, "seed") ?? 0), fixed: fixed !== null };
}

export const connectedOverviewRefine = connectedRefineForDirector;

export const OVERVIEW_STYLES = `
.cstk-overview{--cs-bg:#171c1b;--cs-surface:#202724;--cs-border:#45534b;--cs-text:#e8eeea;--cs-muted:#b2bfb6;--cs-accent:#8ce0b2;--cs-warn:#f1c77c;--cs-error:#ffa5a5;color:var(--cs-text);background:var(--cs-bg);border:1px solid var(--cs-border);border-radius:12px;flex:0 0 auto;font:13px/1.5 ui-sans-serif,system-ui,sans-serif;min-width:0;overflow:hidden}
.cstk-overview *{box-sizing:border-box}.cstk-overview summary{padding:10px 12px;cursor:pointer;display:flex;gap:12px;align-items:center;list-style:none}.cstk-overview summary::-webkit-details-marker{display:none}.cstk-overview .cs-chevron{width:16px;height:16px;transition:transform .18s ease;flex:none}.cstk-overview[open]>.cs-head .cs-chevron{transform:rotate(90deg)}
.cstk-overview .cs-head b{font-size:14px}.cstk-overview .cs-count{color:var(--cs-muted);margin-left:auto;font-variant-numeric:tabular-nums}.cstk-overview .cs-controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:0 12px 10px;border-bottom:1px solid var(--cs-border)}
.cstk-overview label{display:flex;align-items:center;gap:6px}.cstk-overview select,.cstk-overview input[type=text]{border:1px solid var(--cs-border);border-radius:6px;background:var(--cs-surface);color:var(--cs-text);padding:6px 8px;font:inherit;min-width:0;min-height:34px;caret-color:var(--cs-accent)}
.cstk-overview button{border:1px solid var(--cs-border);border-radius:6px;background:var(--cs-surface);color:var(--cs-text);padding:6px 10px;min-height:34px;font:inherit;cursor:pointer}.cstk-overview button:hover{background:#303c35}.cstk-overview button:active{background:#394a40}.cstk-overview .cs-queue{background:#254d39;color:#e9fff2;border-color:#75b892;margin-left:auto}.cstk-overview button:disabled{opacity:.5;cursor:not-allowed}
.cstk-overview :is(button,input,select,summary):focus-visible{outline:2px solid var(--cs-accent);outline-offset:2px}.cstk-overview input[type=checkbox]{accent-color:var(--cs-accent);width:18px;height:18px;cursor:pointer}.cstk-overview ::selection{background:#3c6650;color:#fff}
.cstk-overview .cs-run-summary{margin:0;padding:0 12px 10px;font-weight:600}
.cstk-overview .cs-mode{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 12px;background:var(--cs-surface)}
.cstk-overview .cs-mode-buttons{display:flex;gap:6px;flex-wrap:wrap}
.cstk-overview .cs-mode button{min-height:40px;padding:8px 14px;font-weight:600}
.cstk-overview .cs-mode button[aria-pressed=true]{background:#254d39;border-color:var(--cs-accent);color:#e9fff2;box-shadow:inset 0 -2px var(--cs-accent)}
.cstk-overview .cs-recovery{padding:10px 12px;background:#332b1d;color:#f1d6a7}
.cstk-overview .cs-recovery[hidden]{display:none}
.cstk-overview .cs-recovery p{margin:0 0 8px;white-space:pre-line;overflow-wrap:anywhere}
.cstk-overview .cs-recovery-actions{display:flex;gap:8px;flex-wrap:wrap}
.cstk-overview .cs-recovery small{display:block;margin-top:8px}
.cstk-overview .cs-hint{margin:0;padding:8px 12px;color:var(--cs-muted)}.cstk-overview .cs-message{margin:0;padding:0 12px 10px;color:var(--cs-muted)}.cstk-overview .cs-message[data-tone=error]{color:var(--cs-error)}.cstk-overview .cs-message[data-tone=ok]{color:var(--cs-accent)}
.cstk-overview .cs-list{max-height:260px;overflow:auto;scrollbar-color:var(--cs-border) var(--cs-bg);scrollbar-width:thin}.cstk-overview .cs-row{display:grid;grid-template-columns:24px 52px minmax(110px,1fr) minmax(175px,220px) minmax(170px,1fr);gap:10px;align-items:center;padding:10px 12px;border-top:1px solid #303a34}.cstk-overview .cs-row:first-child{border-top:0}.cstk-overview .cs-row[data-selected=true]{background:#27362d}.cstk-overview .cs-row[data-running=true]{outline:1px solid var(--cs-accent);outline-offset:-1px}
.cstk-overview .cs-thumb{width:52px;height:38px;border-radius:4px;object-fit:cover;background:var(--cs-surface)}.cstk-overview .cs-thumb-empty{display:grid;place-items:center;color:var(--cs-muted);font-variant-numeric:tabular-nums}.cstk-overview .cs-title{padding:0;border:0;min-height:28px;background:transparent!important;text-align:left;font-weight:650;display:block;max-width:100%;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}.cstk-overview .cs-meta,.cstk-overview .cs-source{color:var(--cs-muted);font-size:12px;font-variant-numeric:tabular-nums}.cstk-overview .cs-seed{display:grid;gap:4px;min-width:0}.cstk-overview .cs-seed>label{display:block!important;font-size:12px!important}.cstk-overview .cs-seed input{width:100%!important;max-width:100%;font-variant-numeric:tabular-nums}.cstk-overview .cs-seed-foot{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.cstk-overview .cs-pin{font-size:11px;min-height:24px;padding:2px 5px}.cstk-overview .cs-state{font-size:12px}.cstk-overview .cs-state[data-tone=ok]{color:var(--cs-accent)}.cstk-overview .cs-state[data-tone=warn]{color:var(--cs-warn)}.cstk-overview .cs-state[data-tone=error]{color:var(--cs-error)}
.cstk-overview .cs-diff{font-size:12px;min-width:0;overflow-wrap:anywhere}.cstk-overview .cs-diff summary{padding:3px 0;text-decoration:underline;text-underline-offset:3px;color:var(--cs-warn)}.cstk-overview .cs-diff-body{white-space:pre-wrap;color:var(--cs-muted)}.cstk-overview .cs-empty{padding:18px 12px;color:var(--cs-muted)}
.cstk-director .bd-prompt,.cstk-director .bd-token-editor{font-size:13px;line-height:1.6}.cstk-director .bd-btn:focus-visible{outline:2px solid #8ce0b2;outline-offset:2px}
@media(max-width:1000px){.cstk-overview .cs-row{grid-template-columns:24px 44px minmax(120px,1fr) minmax(175px,1fr)}.cstk-overview .cs-cache{grid-column:3/-1}.cstk-overview .cs-thumb{width:44px}}
@media(max-width:620px){.cstk-overview .cs-row{grid-template-columns:24px 44px minmax(0,1fr)}.cstk-overview .cs-seed,.cstk-overview .cs-cache{grid-column:3}.cstk-overview .cs-controls{gap:8px}.cstk-overview .cs-queue{margin-left:0}.cstk-overview .cs-seed-foot{align-items:flex-start}.cstk-overview .cs-title{white-space:normal}}
@media(prefers-reduced-motion:reduce){.cstk-overview .cs-chevron{transition:none}}
.cstk-overview{container-type:inline-size}
@container(max-width:1000px){.cstk-overview .cs-row{grid-template-columns:24px 44px minmax(120px,1fr) minmax(175px,1fr)}.cstk-overview .cs-cache{grid-column:3/-1}.cstk-overview .cs-thumb{width:44px}}
@container(max-width:620px){.cstk-overview .cs-row{grid-template-columns:24px 44px minmax(0,1fr)}.cstk-overview .cs-seed,.cstk-overview .cs-cache{grid-column:3}.cstk-overview .cs-controls{gap:8px}.cstk-overview .cs-queue{margin-left:0}.cstk-overview .cs-seed-foot{align-items:flex-start}.cstk-overview .cs-title{white-space:normal}}
`;

export class DirectorOverview {
    constructor(editor) {
        this.editor = editor; this.node = editor.node; this.rows = new Map(); this.seq = 0;
        this.data = null; this.busy = false; this.disposed = false; this.signature = "";
        this.root = document.createElement("details"); this.root.open = true; this.root.className = "cstk-overview";
        this.root.innerHTML = `<style>${OVERVIEW_STYLES}</style><summary class="cs-head"><svg class="cs-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m6 3 5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg><b></b><span class="cs-count"></span></summary><div class="cs-controls"><label class="cs-scope"><span></span><select><option value="all"></option><option value="selected"></option></select></label><button type="button" class="cs-refresh"></button></div><p class="cs-run-summary"></p><div class="cs-mode"><span></span><div class="cs-mode-buttons" role="group"><button type="button" data-mode="first_pass"></button><button type="button" data-mode="refine_only"></button><button type="button" data-mode="legacy"></button></div><button type="button" class="cs-queue"></button></div><p class="cs-hint"></p><div class="cs-recovery" hidden role="status" aria-live="polite"><p></p><div class="cs-recovery-actions"><button type="button" data-fix="first_pass"></button><button type="button" data-fix="refine_only"></button><button type="button" data-fix="inspect"></button><button type="button" data-fix="retry"></button></div><small></small></div><div class="cs-list"></div><p class="cs-message" role="status" aria-live="polite"></p>`;
        this.scope = this.root.querySelector(".cs-scope select"); this.modeButtons = [...this.root.querySelectorAll("[data-mode]")];
        this.recovery = this.root.querySelector(".cs-recovery");
        this.list = this.root.querySelector(".cs-list"); this.message = this.root.querySelector(".cs-message");
        this.queue = this.root.querySelector(".cs-queue"); this.refresh = this.root.querySelector(".cs-refresh");
        const toolbar = editor.root.querySelector(".bd-toolbar-wrap"); toolbar?.after(this.root);
        editor.root.classList.add("cstk-director");
        this.scope.onchange = () => {
            const enabled = this.scope.value === "selected";
            editor.timeline.runSelectEnabled = enabled;
            if (enabled && !editor.timeline.runSelection?.length) editor.timeline.runSelection = overviewRows(editor).map((_, i) => i);
            editor.commit(false, { syncTimeline: true }); this.invalidate(200);
        };
        for (const button of this.modeButtons) button.onclick = () => this.setMode(button.dataset.mode);
        for (const button of this.recovery.querySelectorAll("[data-fix]")) button.onclick = () => {
            if (button.dataset.fix === "inspect") this.showProblems();
            else if (button.dataset.fix === "retry") this.checkCache();
            else this.setMode(button.dataset.fix);
        };
        this.refresh.onclick = () => this.checkCache(); this.queue.onclick = () => this.submit();
        this.root.addEventListener("toggle", () => editor.updateDomWidgetHeight?.());
        for (const event of ["pointerdown", "mousedown", "click", "keydown", "keyup", "wheel"]) {
            this.root.addEventListener(event, (e) => e.stopPropagation());
        }
        this.unsub = onLocaleChange(() => { this.update(); });
        this.onExecuted = () => this.invalidate(400);
        api.addEventListener?.("executed", this.onExecuted);
        this.update(); this.invalidate(250);
    }

    settingsSignature() {
        const rows = overviewRows(this.editor).map((r) => {
            const { previewB64, previewFrames, ...settings } = r;
            return settings;
        });
        const names = ["seed", "steps", "cfg", "sampler", "scheduler", "shift_video", "shift_audio", "cache_name", "width", "height", "frame_rate", "task_type", "global_prompt", "total_frames", "ref_max_size"];
        const refine = connectedOverviewRefine(this.node);
        return JSON.stringify([rows, this.editor.timeline.global, this.editor.timeline.output,
            names.map((name) => widget(this.node, name)?.value), this.editor.timeline.runSelectEnabled,
            this.editor.timeline.runSelection, this.editor.timeline.executionMode,
            this.node.inputs?.map(({name, link}) => [name, link]), refine?.id,
            refine?.widgets?.map(({name, value}) => [name, value]), refine?.inputs?.map(({name, link}) => [name, link])],
            (key, value) => key === "previewB64" || key === "previewFrames" ? undefined : value);
    }

    invalidate(delay = 400) {
        if (this.disposed) return;
        this.seq++; this.data = null; this.checking = false;
        this.queueNotice = ""; this.submitError = "";
        this.updateStates(); clearTimeout(this.timer);
        this.timer = setTimeout(() => this.checkCache(), delay);
    }

    update() {
        if (this.disposed) return;
        this.root.querySelector(".cs-head b").textContent = label("title");
        this.root.querySelector(".cs-head").title = label("collapse");
        this.root.querySelector(".cs-scope span").textContent = label("scope");
        this.root.querySelector(".cs-mode span").textContent = label("stage");
        for (const option of this.scope.options) option.textContent = label(option.value);
        this.root.querySelector(".cs-mode-buttons").setAttribute("aria-label", label("stage"));
        for (const button of this.modeButtons) {
            button.textContent = label(button.dataset.mode);
            button.setAttribute("aria-pressed", String(button.dataset.mode === (this.editor.timeline.executionMode || "legacy")));
        }
        this.scope.value = this.editor.timeline.runSelectEnabled && overviewRows(this.editor).length > 1 ? "selected" : "all";
        this.refresh.textContent = this.checking ? label("checking") : label("refresh");
        this.queue.textContent = this.busy ? label("submitting") : label("queue");
        const rows = overviewRows(this.editor), present = new Set();
        this.root.querySelector(".cs-count").textContent = `${rows.length} ${label("count")} · ${rows.filter((_, i) => this.runEnabled(i)).length} ${label("selected")}`;
        this.scope.disabled = rows.length < 2;
        rows.forEach((row, index) => {
            const key = `${row.id || "segment"}:${index}`; present.add(key);
            let view = this.rows.get(key);
            if (!view) { view = this.makeRow(index); this.rows.set(key, view); }
            view.row = row; view.index = index;
            view.root.dataset.selected = String(index === this.editor.selectedIndex);
            view.root.dataset.running = String(index === this.editor._runHighlightSeg);
            view.check.checked = this.runEnabled(index); view.check.disabled = !this.editor.timeline.runSelectEnabled || rows.length < 2;
            view.check.setAttribute("aria-label", `${label("selected")} ${label("segment")} ${index + 1}`);
            view.title.textContent = `${label("segment")} ${index + 1}`; view.title.title = label("edit");
            const fps = Number(this.editor.getFrameRate?.() || this.editor.timeline.frameRate || 24);
            const frames = Number(row.frameCount || row.length || 0);
            const sec = frames ? frames / fps : Number(row.durationSec || 0);
            view.meta.textContent = `${sec.toFixed(2)} s · ${frames || "—"} f${index === this.editor._runHighlightSeg ? ` · ${label("running")}` : ""}`;
            const input = view.seed.querySelector("input");
            if (document.activeElement !== input) input.value = row.first_pass_seed ?? "";
            view.seed.firstChild.firstChild.textContent = label("seed"); input.placeholder = label("inherit"); input.setAttribute("aria-label", `${label("segment")} ${index + 1} ${label("seed")}`);
            input.disabled = Boolean(row.externalSeedLinked); input.title = input.disabled ? label("linked") : label("inherit");
            try {
                const effective = effectiveSegmentSeed(row, this.node);
                view.source.textContent = `${label(effective.fixed ? "fixed" : "global")} · ${effective.value}`;
                view.pin.hidden = effective.fixed || input.disabled;
                const inherited = widgetValue(this.node, "seed");
                view.pin.disabled = typeof inherited === "number" && !Number.isSafeInteger(inherited);
                view.pin.title = view.pin.disabled ? label("pinUnsafe") : "";
            } catch { view.source.textContent = label("invalidSeed"); view.pin.hidden = true; }
            view.pin.textContent = label("pin");
            this.setThumbnail(view, row, index);
            if (this.list.children[index] !== view.root) this.list.insertBefore(view.root, this.list.children[index] || null);
        });
        for (const [key, view] of this.rows) if (!present.has(key)) { view.root.remove(); this.rows.delete(key); }
        this.list.querySelector(".cs-empty")?.remove();
        if (!rows.length) { const empty = document.createElement("div"); empty.className = "cs-empty"; empty.textContent = label("empty"); this.list.append(empty); }
        const signature = this.settingsSignature();
        if (this.signature && signature !== this.signature) this.invalidate(600);
        this.signature = signature;
        syncSegmentSeedControls(this.editor.root);
        this.updateStates();
    }

    makeRow(index) {
        const root = document.createElement("div"); root.className = "cs-row";
        root.innerHTML = `<input type="checkbox"><div class="cs-thumb cs-thumb-empty"></div><div><button type="button" class="cs-title"></button><div class="cs-meta"></div></div><div class="cs-seed"></div><div class="cs-cache"><div class="cs-state"></div><div class="cs-meta cs-final"></div><details class="cs-diff" hidden><summary></summary><div class="cs-diff-body"></div></details></div>`;
        const view = { root, index, check: root.querySelector("input"), title: root.querySelector(".cs-title"),
            meta: root.querySelector(".cs-meta"), seed: root.querySelector(".cs-seed"), state: root.querySelector(".cs-state"),
            final: root.querySelector(".cs-final"), diff: root.querySelector(".cs-diff") };
        const control = createSegmentSeedControl(() => view.row, () => {
            this.editor.writeExternalGroupSeed?.(view.index, view.row.first_pass_seed);
            if (this.editor.isFl2vMode?.()) syncFl2vFromShots(this.editor);
            this.editor.flushTimelineSync(); this.update(); this.invalidate(650);
        }, { label: label("seed"), placeholder: label("inherit") });
        view.seed.append(control);
        const foot = document.createElement("div"); foot.className = "cs-seed-foot";
        view.source = document.createElement("span"); view.source.className = "cs-source";
        view.pin = document.createElement("button"); view.pin.type = "button"; view.pin.className = "cs-pin";
        view.pin.onclick = () => {
            const input = control.querySelector("input"); input.value = effectiveSegmentSeed(view.row, this.node).value;
            input.dispatchEvent(new Event("input", { bubbles: true }));
        };
        foot.append(view.source, view.pin); view.seed.append(foot);
        view.check.onchange = () => this.editor.toggleSegmentRun(view.index);
        view.title.onclick = () => {
            this.editor.flushTimelineSync(); this.editor.selectedIndex = view.index;
            this.editor.timeline.editMode = "segment";
            if (this.editor.isImageBatch?.()) this.editor.renderImageBatchGroups();
            else this.editor.updateSelectionUI();
            this.editor.scheduleRender?.(); this.update();
        };
        return view;
    }

    setThumbnail(view, row, index) {
        let source = row.previewB64 || row.previewFrames?.[0];
        if (source && !String(source).startsWith("data:")) source = `data:${row.previewMime || "image/jpeg"};base64,${source}`;
        if (!source) {
            const ref = row.startImage || row.refs?.find((r) => r.imageFile);
            if (ref?.imageFile) source = `/view?${new URLSearchParams({ filename: ref.imageFile, subfolder: ref.subfolder || "", type: ref.type || "input" })}`;
        }
        if (view.thumbInitialized && source === view.thumbSource) return;
        view.thumbInitialized = true; view.thumbSource = source;
        const old = view.root.querySelector(".cs-thumb");
        if (source) {
            const image = document.createElement("img"); image.className = "cs-thumb"; image.alt = `${label("segment")} ${index + 1}`; image.loading = "lazy";
            image.src = source; image.onerror = () => { image.removeAttribute("src"); image.alt = label("missing"); };
            old.replaceWith(image);
        } else {
            const placeholder = document.createElement("div"); placeholder.className = "cs-thumb cs-thumb-empty";
            placeholder.textContent = String(index + 1); old.replaceWith(placeholder);
        }
    }

    updateStates() {
        const records = new Map((this.data?.segments || []).map((r) => [Number(r.segment) - 1, r]));
        for (const view of this.rows.values()) {
            const cached = records.get(view.index); let text = this.checking ? label("checking") : label("unknown"), tone = "muted";
            if (cached) {
                if (cached.matches) { text = label("matched"); tone = "ok"; }
                else if (cached.error) { text = label("damaged"); tone = "error"; }
                else if (!cached.exists) { text = label("missing"); tone = "warn"; }
                else { text = label("mismatch"); tone = "warn"; }
            }
            view.state.textContent = text; view.state.dataset.tone = tone;
            view.final.textContent = cached ? label(cached.final_exists ? "final" : "noFinal") : "";
            view.diff.hidden = !cached || cached.matches;
            view.diff.querySelector("summary").textContent = label("details");
            const differences = cached?.differences || [];
            view.diff.querySelector(".cs-diff-body").textContent = [cached?.error,
                ...(cached?.diff_keys || []).map((key) => this.diffName(key)),
                cached?.cached_seed_text != null ? `${label("previous")} seed: ${cached.cached_seed_text} → ${label("current")}: ${cached.expected_seed_text}` : "",
                ...differences.filter((d) => d.key !== "seed").map((d) => `${this.diffName(d.key)}: ${d.cached} → ${d.current}`),
            ].filter(Boolean).join("\n");
        }
        this.refresh.disabled = this.checking;
        this.updateAction();
    }

    diffName(key) {
        return getLocale() === "en" ? key : diffLabel(key);
    }

    updateAction() {
        const mode = this.editor.timeline.executionMode || "legacy";
        this.root.querySelector(".cs-hint").textContent = label(mode === "legacy" ? "legacyHint" : mode === "first_pass" ? "firstHint" : "refineHint");
        let reason = "", ready = false;
        const output = this.editor.timeline.output || {};
        const refineNode = connectedOverviewRefine(this.node);
        const confirm = widgetValue(refineNode, "confirm_first_pass");
        this.stageConflict = mode === "legacy" && output.rollingGeneration === true
            && output.exportMode !== "segments" && Boolean(refineNode)
            && (confirm === true || confirm === 1 || String(confirm).toLowerCase() === "true");
        const rows = overviewRows(this.editor);
        if (!rows.length || !rows.some((_, i) => this.runEnabled(i))) reason = label("noSelection");
        try { rows.forEach((row) => normalizeSegmentSeed(row.first_pass_seed)); } catch { reason = label("invalidSeed"); }
        if (mode === "refine_only") {
            const refine = connectedOverviewRefine(this.node);
            if (!refine || !["refine", "upscale"].includes(widgetValue(refine, "mode"))
                || refine.inputs?.find((i) => i.name === "sigmas")?.link == null) reason = label("noRefine");
            else if (!this.data?.can_confirm_refine) reason = this.cacheError || label(!this.data ? "stale" : this.data.confirm_refine_reason === "refine_skipped" ? "skipped" : "blocked");
            else ready = true;
        }
        if (this.stageConflict && !reason) reason = label("conflict");
        if (typeof app.queuePrompt !== "function") reason = label("noQueue");
        this.root.querySelector(".cs-run-summary").textContent = label("runSummary")
            .replace("{n}", rows.filter((_, i) => this.runEnabled(i)).length)
            .replace("{memory}", label(output.rollingGeneration ? "rollingName" : output.lowMemoryMode ? "diskName" : "normalName"))
            .replace("{export}", label(output.exportMode === "segments" ? "segmentExport" : "allExport"));
        this.recovery.hidden = !reason;
        this.recovery.querySelector("p").textContent = reason;
        this.recovery.querySelector("small").textContent = label("actionNote");
        const fixes = {first_pass: "chooseFirst", refine_only: "chooseSecond", inspect: "inspect", retry: "retry"};
        for (const button of this.recovery.querySelectorAll("[data-fix]")) {
            const fix = button.dataset.fix;
            button.textContent = label(fixes[fix]);
            button.hidden = this.stageConflict ? !["first_pass", "refine_only"].includes(fix)
                : mode === "refine_only" ? fix === "refine_only" : fix !== "inspect";
        }
        this.blockReason = reason;
        this.queue.disabled = this.busy || Boolean(reason);
        this.message.dataset.tone = this.cacheError || this.submitError ? "error" : ready || this.queueNotice ? "ok" : "muted";
        this.message.textContent = (reason ? "" : this.submitError) || this.cacheError || this.queueNotice || (ready ? label("ready") : label("scopeHint"));
        if (this.editor.timeline.output?.rollingGeneration === true) this.message.textContent += ` ${label(this.editor.timeline.output?.exportMode === "segments" ? "rolling" : "rollingAll")}`;
        else if (this.editor.timeline.output?.lowMemoryMode === true) this.message.textContent += ` ${label("lowMemory")}`;
        this.queue.title = reason || label("scopeHint");
    }

    setMode(mode) {
        if (!["legacy", "first_pass", "refine_only"].includes(mode)) return;
        this.editor.timeline.executionMode = mode;
        this.editor.flushTimelineSync(); this.invalidate(100); this.update();
    }

    showProblems() {
        for (const view of this.rows.values()) if (this.runEnabled(view.index) && !view.diff.hidden) view.diff.open = true;
        const problem = [...this.rows.values()].find(v => this.runEnabled(v.index) && !v.diff.hidden);
        (problem?.root || this.list).scrollIntoView({block: "nearest"});
    }

    revealProblem() {
        this.root.open = true;
        app.canvas?.centerOnNode?.(this.node);
        this.root.scrollIntoView({block: "nearest"});
        const target = [...this.recovery.querySelectorAll("button")].find(b => !b.hidden);
        target?.focus({preventScroll: true});
    }

    async prepareRun() {
        this.editor.flushTimelineSync(); this.update();
        const signature = this.settingsSignature();
        if (this.editor.timeline.executionMode === "refine_only") {
            const accepted = await this.checkCache();
            if (!accepted || signature !== this.settingsSignature() || this.disposed) {
                this.submitError = this.cacheError || label("changed"); this.updateAction();
                this.revealProblem(); return false;
            }
        }
        this.updateAction();
        if (this.blockReason) { this.revealProblem(); return false; }
        return true;
    }

    runEnabled(index) { return overviewRows(this.editor).length < 2 || this.editor.isSegmentRunEnabled(index); }

    async checkCache() {
        if (this.disposed) return false;
        clearTimeout(this.timer); const seq = ++this.seq; this.checking = true; this.data = null; this.cacheError = ""; this.update();
        const signature = this.settingsSignature();
        try {
            const payload = cacheStatusPayload(this.node, connectedOverviewRefine(this.node));
            const response = await api.fetchApi("/cinestack/h3/first_pass_cache_status", {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (seq !== this.seq || this.disposed || signature !== this.settingsSignature()) return false;
            if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
            this.data = data;
            return true;
        } catch (error) { if (seq === this.seq) this.cacheError = `${label("failed")}: ${error.message || error}`; }
        finally { if (seq === this.seq && !this.disposed) { this.checking = false; this.update(); } }
    }

    async submit() {
        if (this.busy || this.disposed) return;
        this.updateAction();
        if (this.blockReason) return;
        this.busy = true; this.submitError = ""; this.queueNotice = ""; this.update();
        const signature = this.settingsSignature();
        try {
            if (this.editor.timeline.executionMode === "refine_only") {
                const accepted = await this.checkCache(); this.updateAction();
                if (!accepted || this.blockReason || signature !== this.settingsSignature() || this.disposed) {
                    this.submitError = label("changed"); return;
                }
            }
            this.editor.flushTimelineSync();
            const result = await app.queuePrompt(0, 1);
            if (result === false) this.submitError = label("notConfirmed");
            else this.queueNotice = label("queued");
        }
        catch (error) { this.submitError = String(error.message || error); }
        finally { this.busy = false; this.queue.textContent = label("queue"); this.updateAction(); }
    }

    dispose() { this.disposed = true; this.seq++; clearTimeout(this.timer); this.unsub?.(); api.removeEventListener?.("executed", this.onExecuted); this.root.remove(); }
}

export function mountDirectorOverview(editor) { return new DirectorOverview(editor); }


// Remember output definitions so unused Directors do not block unrelated work.
const outputNodeTypes = new Set();
export function rememberQueueNodeDefinition(definition) {
    if (definition?.output_node === true) outputNodeTypes.add(definition.name);
}

export async function preflightDirectorQueue(args = []) {
    const graph = app.rootGraph || app.graph || app.canvas?.graph;
    let candidates = (graph?._nodes || graph?.nodes || [])
        .filter(node => node.mode == null || node.mode === 0)
        .map(node => node._cineStackEditor?.overview).filter(view => view && !view.disposed);
    if (!candidates.length) return true;
    const signatures = new Map(candidates.map(view => [view, view.settingsSignature()]));
    if (typeof app.graphToPrompt === "function") {
        let prompt;
        try { prompt = await app.graphToPrompt(graph); }
        catch { return true; } // Let the host display its own serialization error.
        const output = prompt?.output || {};
        const options = args[2];
        const targets = Array.isArray(options) ? options : options?.queueNodeIds;
        const roots = targets?.length ? targets.map(String)
            : Object.keys(output).filter(id => outputNodeTypes.has(output[id].class_type));
        let active = new Set(Object.keys(output));
        if (roots.length || outputNodeTypes.size) {
            active = new Set();
            const visit = id => {
                if (active.has(id) || !output[id]) return;
                active.add(id);
                for (const value of Object.values(output[id].inputs || {})) {
                    if (Array.isArray(value) && value.length === 2 && typeof value[1] === "number") visit(String(value[0]));
                }
            };
            roots.forEach(visit);
        }
        candidates = candidates.filter(view => active.has(String(view.node.id)));
    }
    for (const view of candidates) {
        if (view.settingsSignature() !== signatures.get(view)) {
            view.submitError = label("changed"); view.updateAction(); view.revealProblem(); return false;
        }
        if (!await view.prepareRun()) return false;
    }
    // An earlier Director can change while a later one's cache is being checked.
    for (const view of candidates) {
        if (view.disposed || graph !== (app.rootGraph || app.graph || app.canvas?.graph)
            || view.settingsSignature() !== signatures.get(view)) {
            view.submitError = label("changed"); view.updateAction(); view.revealProblem(); return false;
        }
    }
    return true;
}

export function installDirectorQueueGuard(flushDirectors, clearRunStatus) {
    if (!app.queuePrompt || app.queuePrompt._cineStackPatched) return;
    const original = app.queuePrompt;
    let checking = false;
    app.queuePrompt = async function (...args) {
        if (checking) return false;
        checking = true;
        try {
            flushDirectors();
            if (!await preflightDirectorQueue(args)) return false;
            clearRunStatus();
            return await original.apply(this, args);
        } finally { checking = false; }
    };
    app.queuePrompt._cineStackPatched = true;
}
