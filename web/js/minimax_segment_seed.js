/** Decimal strings keep uint64 seeds exact across JS, JSON and Python. */
export function normalizeSegmentSeed(value) {
    if (value == null || String(value).trim() === "") return null;
    if (typeof value === "number" && !Number.isSafeInteger(value)) {
        throw new Error("Seed must be entered as a decimal string above 2^53.");
    }
    const text = String(value).trim();
    if (!/^[0-9]+$/.test(text) || BigInt(text) > 18446744073709551615n) {
        throw new Error("Seed must be an integer from 0 to 18446744073709551615.");
    }
    return BigInt(text).toString();
}

export function syncSegmentSeedControls(root) {
    for (const control of root?.querySelectorAll?.("[data-cstk-seed-control]") || []) {
        const input = control.querySelector("input");
        const row = control._cstkSeedRow?.();
        if (input && document.activeElement !== input) input.value = row?.first_pass_seed ?? "";
        if (input) {
            input.disabled = Boolean(row?.externalSeedLinked);
            try { normalizeSegmentSeed(row?.first_pass_seed); input.setCustomValidity(""); }
            catch (error) { input.setCustomValidity(error.message); }
        }
    }
}

export function createSegmentSeedControl(getRow, onChange, labels = {}) {
    const label = document.createElement("label");
    label.dataset.cstkSeedControl = "true";
    label._cstkSeedRow = getRow;
    label.style.cssText = "display:flex;align-items:center;gap:6px;min-width:0;font-size:11px";
    label.textContent = labels.label || "First-pass seed";
    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "numeric";
    input.className = "bd-num";
    input.placeholder = labels.placeholder || "Inherit global";
    input.setAttribute("aria-label", label.textContent);
    input.title = labels.hint || "Empty inherits the global seed. A value fixes this segment's first-pass seed.";
    input.style.cssText = "min-width:80px;width:150px;max-width:100%;flex:1";
    input.value = getRow()?.first_pass_seed ?? "";
    input.disabled = !!getRow()?.externalSeedLinked;
    input.addEventListener("input", () => {
        const row = getRow();
        if (!row) return;
        try {
            row.first_pass_seed = normalizeSegmentSeed(input.value);
            input.setCustomValidity("");
        } catch (error) {
            // Preserve invalid drafts too: Queue must reject them, never silently
            // sample the previous seed while showing a different value on screen.
            row.first_pass_seed = input.value;
            input.setCustomValidity(error.message);
        }
        onChange?.();
        syncSegmentSeedControls(label.closest(".bd-wrap") || label.parentElement);
    });
    input.addEventListener("change", () => {
        if (!input.reportValidity()) return;
        input.value = getRow()?.first_pass_seed ?? "";
    });
    for (const event of ["pointerdown", "click", "keydown", "keyup"]) {
        label.addEventListener(event, (e) => e.stopPropagation());
    }
    label.appendChild(input);
    return label;
}
