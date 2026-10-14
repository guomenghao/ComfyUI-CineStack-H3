// CineStack legacy workflow migration; no global aliases or upstream node interception.
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

export const LEGACY_NODE_IDS = {
    "MiniMaxH3Director": "CineStackH3Director",
    "MiniMaxH3DirectorRefine": "CineStackH3DirectorRefine",
    "MiniMaxH3DirectorSelfLift": "CineStackH3DirectorSelfLift",
    "MiniMaxH3DirectorSemanticBridge": "CineStackH3DirectorSemanticBridge",
    "MiniMaxH3DirectorFaceRefine": "CineStackH3DirectorFaceRefine",
    "ComfyMiniMaxH3Director": "CineStackH3Director",
    "MiniMaxH3DirectorConditioning": "CineStackH3DirectorConditioning",
    "MiniMaxH3DirectorPlannerConditioning": "CineStackH3DirectorPlannerConditioning",
    "MiniMaxH3DirectorGroupImageToVideo": "CineStackH3DirectorGroupImageToVideo",
    "MiniMaxH3DirectorGroupReferenceToVideo": "CineStackH3DirectorGroupReferenceToVideo",
    "MiniMaxH3DirectorGroupsCombine": "CineStackH3DirectorGroupsCombine"
};

const CINESTACK_NODE_IDS = new Set(Object.values(LEGACY_NODE_IDS));
let installedVersion = null;
let versionRequest = null;

export async function loadInstalledVersion() {
    if (installedVersion) return installedVersion;
    if (!versionRequest) {
        versionRequest = (async () => {
            try {
                const response = await api.fetchApi("/cinestack/h3/version", {
                    cache: "no-store", signal: AbortSignal.timeout(5000),
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                if (data.package !== "cinestack-h3" || !/^\d+\.\d+\.\d+$/.test(data.version ?? "")) {
                    throw new Error("Invalid CineStack version response");
                }
                installedVersion = data.version;
                return installedVersion;
            } catch (error) {
                // Preserve saved metadata if the server cannot identify itself.
                console.warn("[CineStack] Cannot read installed version; restart/update ComfyUI if needed.", error);
                return null;
            }
        })();
    }
    try { return await versionRequest; }
    finally { versionRequest = null; }
}

export function syncNodeVersion(node, version = installedVersion, type = node?.comfyClass ?? node?.type) {
    if (!CINESTACK_NODE_IDS.has(type) || !version) return false;
    node.properties ??= {};
    Object.assign(node.properties, {"Node name for S&R": type,
        cnr_id: "cinestack-h3", ver: version, aux_id: "guomenghao/ComfyUI-CineStack-H3"});
    return true;
}

export function migrateWorkflowInPlace(data, isRegistered = () => false, version = installedVersion) {
    let changed = 0;
    const migrateNode = (node, key) => {
        const legacy = node?.[key];
        if (!node || typeof node !== "object") return;
        if (Object.hasOwn(LEGACY_NODE_IDS, legacy) && !isRegistered(legacy)) {
            node[key] = LEGACY_NODE_IDS[legacy];
            changed++;
        }
        if (key === "type") syncNodeVersion(node, version, node[key]);
    };
    const visit = (graph) => {
        if (!graph || typeof graph !== "object") return;
        for (const node of graph.nodes ?? []) migrateNode(node, "type");
        for (const subgraph of graph.definitions?.subgraphs ?? []) visit(subgraph);
        for (const group of Object.values(graph.extra?.groupNodes ?? {})) visit(group);
    };
    visit(data);
    const prompt = data?.prompt ?? data;
    if (prompt && typeof prompt === "object") {
        for (const node of Object.values(prompt)) migrateNode(node, "class_type");
    }
    return changed;
}

app.registerExtension({
    name: "CineStack.H3.WorkflowMigration",
    async setup() {
        await loadInstalledVersion();
        for (const node of app.graph?._nodes ?? []) syncNodeVersion(node);
    },
    async beforeConfigureGraph(graphData) {
        await loadInstalledVersion();
        // With both plugins installed, leave upstream workflows with upstream.
        const registered = globalThis.LiteGraph?.registered_node_types ?? {};
        const count = migrateWorkflowInPlace(graphData, id => Object.hasOwn(registered, id));
        if (count) console.info(`[CineStack] Migrated ${count} legacy Director nodes in memory.`);
    },
    nodeCreated(node) { syncNodeVersion(node); },
    loadedGraphNode(node) { syncNodeVersion(node); },
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (!CINESTACK_NODE_IDS.has(nodeData.name)) return;
        const configure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (...args) {
            const result = configure?.apply(this, args);
            // configure/paste restores properties after nodeCreated runs.
            syncNodeVersion(this, installedVersion, nodeData.name);
            return result;
        };
    },
});
