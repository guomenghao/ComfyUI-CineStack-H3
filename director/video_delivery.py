"""Expose durable rolling files without opening or decoding full video frames."""
from pathlib import Path
import logging
import json

log = logging.getLogger('ComfyUI-CineStack-H3.video_delivery')


def rolling_video_results(run):
    full = bool(run.store and run.store.full)
    source = (run.full_export or {}).get('merged', {}) if full else run.merged
    results = []
    import folder_paths
    output = Path(folder_paths.get_output_directory()).resolve()
    for stage in ('first', 'final'):
        record = source.get(stage)
        item = {'stage': stage, 'scope': 'timeline' if full else 'selected',
                'available': False, 'complete': False}
        if not record:
            item['reason'] = ((run.full_export or {}).get('unavailable', {}).get(stage)
                              or ('本轮没有生成一采视频。' if stage == 'first' else '本轮尚未生成最终视频。'))
        else:
            path = Path(record['path']).resolve()
            try:
                relative = path.relative_to(output)
                if not path.is_file():
                    raise FileNotFoundError(path.name)
            except (ValueError, OSError):
                item['reason'] = '输出视频已不存在或不在 ComfyUI output 目录内；请检查本轮 report。'
            else:
                item.update(available=True, complete=bool(record['complete']),
                            filename=relative.name, subfolder=relative.parent.as_posix(),
                            type='output', path=str(path))
        results.append(item)
    return results


def finalize_video_delivery(plan, outputs):
    """Append two ports; old eight outputs and their indices remain unchanged."""
    from comfy_execution.graph_utils import ExecutionBlocker
    from .execution_mode import rolling_enabled
    rows = getattr(plan, '_rolling_video_results', []) if rolling_enabled(plan) else []
    videos = []
    for stage in ('first', 'final'):
        item = next((row for row in rows if row['stage'] == stage), None)
        video = ExecutionBlocker(None)
        if item and item.get('available'):
            try:
                from comfy_api.latest import InputImpl
                # Official constructor stores the path only; no BytesIO/read_bytes/get_components.
                video = InputImpl.VideoFromFile(item['path'])
            except (ImportError, AttributeError) as exc:
                item['port_warning'] = '当前 ComfyUI 不支持文件 VIDEO 接口；可在此预览或下载，更新 ComfyUI 后再连接 SaveVideo。'
                log.warning('File VIDEO interface unavailable: %s', exc)
        videos.append(video)
    return {'ui': {'cinestack_videos': rows}, 'result': tuple(outputs) + tuple(videos)}


def file_video_consumers(prompt, unique_id):
    """Inspect actual API links, including links through reroutes/switches."""
    if not isinstance(prompt, dict) or unique_id is None:
        return ()
    return tuple(sorted(
        (str(node_id), name, value[1])
        for node_id, node in prompt.items() if isinstance(node, dict)
        for name, value in (node.get('inputs') or {}).items()
        if isinstance(value, (list, tuple)) and len(value) == 2
        and str(value[0]) == str(unique_id) and type(value[1]) is int
        and value[1] in (8, 9)
    ))


def validate_file_video_connections(timeline_data, prompt, unique_id):
    """Fail before Director preparation/sampling; never change caches or mode."""
    consumers = file_video_consumers(prompt, unique_id)
    if not consumers:
        return
    raw = json.loads(timeline_data) if isinstance(timeline_data, str) else timeline_data
    if ((raw or {}).get('output') or {}).get('rollingGeneration') is True:
        return
    details = ', '.join(
        f"{'first_pass_video' if slot == 8 else 'final_video'} → #{node}.{name}"
        for node, name, slot in consumers
    )
    raise ValueError(
        f"导演台 #{unique_id} 尚未开始生成：文件视频输出已接线（{details}），但滚动生成未开启。"
        "请在导演台开启「滚动生成（当前段＋上一段）」；已有一采且只想二采时，选择「仅二采」。"
        "若保留普通模式，请改接 IMAGE/AUDIO → CreateVideo → SaveVideo。"
        "未重跑一采，未修改已有缓存。 / File VIDEO outputs require rolling generation."
    )
