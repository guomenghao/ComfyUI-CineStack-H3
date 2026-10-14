"""Read-only, bounded memory observations. Never retain tensors or change allocators."""
from __future__ import annotations

import ctypes
from contextvars import ContextVar
from dataclasses import fields, is_dataclass
from functools import lru_cache
import json
from itertools import islice
import logging
import os
from pathlib import Path
import platform
import sys
import time
import uuid

import torch

log = logging.getLogger("ComfyUI-CineStack-H3.memory")
MIB = 1024 ** 2


def process_snapshot():
    values = {}
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in {'VmRSS', 'RssAnon', 'RssFile', 'RssShmem', 'VmSwap'}:
                values[key] = int(value.split()[0]) * 1024
    except (OSError, ValueError):
        try:
            import psutil
            values['VmRSS'] = psutil.Process().memory_info().rss
        except (ImportError, OSError):
            pass
    return values


class Mallinfo2(ctypes.Structure):
    _fields_ = [(name, ctypes.c_size_t) for name in
                ('arena', 'ordblks', 'smblks', 'hblks', 'hblkhd', 'usmblks',
                 'fsmblks', 'uordblks', 'fordblks', 'keepcost')]


@lru_cache(maxsize=1)
def _mallinfo():
    # Only inspect glibc when it is the default allocator. Never call malloc_trim.
    if platform.system() != 'Linux' or platform.libc_ver()[0] != 'glibc' or os.getenv('LD_PRELOAD'):
        return None
    try:
        function = ctypes.CDLL(None).mallinfo2
        function.restype = Mallinfo2
        function.argtypes = []
        return function
    except (AttributeError, OSError):
        return None


def allocator_snapshot():
    fn = _mallinfo()
    if fn is None:
        return None
    info = fn()
    return {key: int(getattr(info, key)) for key in ('arena', 'uordblks', 'fordblks', 'hblkhd')}


def cgroup_snapshot():
    root = Path('/sys/fs/cgroup')
    try:
        relative = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                        if line.startswith('0::'))
        candidate = root / relative.lstrip('/')
        if '..' not in candidate.parts and (candidate / 'memory.current').is_file():
            root = candidate
    except (OSError, StopIteration):
        pass
    result = {}
    for key in ('memory.current', 'memory.max', 'memory.swap.current'):
        try:
            value = (root / key).read_text().strip()
            result[key] = int(value) if value != 'max' else value
        except (OSError, ValueError):
            pass
    return result


def storage_snapshot(groups, *, max_objects=20000):
    """Count complete backing storages, including sliced views, once across groups.

    This covers supplied tensors only, not arbitrary Python objects or all model
    weights. First group wins attribution. No tensor content/copy/device sync.
    """
    seen, storages, totals = {}, {}, {}
    visited = errors = 0
    truncated = False
    for group, value in groups.items():
        totals[group] = {'cpu': 0, 'other': 0, 'storages': 0}
        stack = [value]
        def add(children):
            nonlocal truncated
            room = max(0, max_objects - visited - len(stack))
            batch = list(islice(children, room + 1))
            if len(batch) > room:
                truncated = True
            stack.extend(batch[:room])
        while stack:
            if visited >= max_objects:
                truncated = True
                break
            obj = stack.pop()
            if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
                continue
            if id(obj) in seen:
                continue
            seen[id(obj)] = obj; visited += 1
            try:
                if isinstance(obj, torch.Tensor):
                    if obj.is_nested:
                        add(iter(obj.unbind()))
                        continue
                    storage = obj.untyped_storage()
                    size = storage.nbytes()
                    key = (str(obj.device), storage.data_ptr(), size)
                    if size and key not in storages:
                        device = 'cpu' if obj.device.type == 'cpu' else 'other'
                        totals[group][device] += size
                        totals[group]['storages'] += 1
                        storages[key] = {'group': group, 'bytes': size, 'device': str(obj.device),
                                         'shape': list(obj.shape), 'dtype': str(obj.dtype)}
                elif isinstance(obj, dict):
                    add(iter(obj.values()))
                elif isinstance(obj, (list, tuple)):
                    add(iter(obj))
                elif type(obj).__module__ == 'comfy.nested_tensor' and type(obj).__name__ == 'NestedTensor':
                    add(iter(obj.unbind()))
                elif is_dataclass(obj) and not isinstance(obj, type):
                    add(getattr(obj, field.name) for field in fields(obj))
            except Exception:
                errors += 1
        if truncated:
            break
    return {'groups': totals, 'cpu_bytes': sum(v['cpu'] for v in totals.values()),
            'other_bytes': sum(v['other'] for v in totals.values()), 'storage_count': len(storages),
            'largest': sorted(storages.values(), key=lambda v: v['bytes'], reverse=True)[:8],
            'visited_objects': visited, 'truncated': truncated, 'unsupported_tensors': errors}


def runtime_snapshot():
    result = {}
    mm = sys.modules.get('comfy.model_management')
    models = getattr(mm, 'current_loaded_models', None)
    if isinstance(models, (list, tuple)):
        result['loaded_model_records'] = len(models)
    # No initialization or synchronization of CUDA just for diagnosis.
    if torch.cuda.is_initialized():
        result.update(cuda_device=torch.cuda.current_device(), cuda_allocated=torch.cuda.memory_allocated(),
                      cuda_reserved=torch.cuda.memory_reserved())
    return result


# The wrapper resets this token even on interruption; no global plan/tensor cache.
SAMPLING_PLAN = ContextVar("cinestack_sampling_plan", default=None)


def record_sampling_memory(stage, **counters):
    plan = SAMPLING_PLAN.get()
    diagnostics = getattr(plan, "_active_memory_diagnostics", None)
    if diagnostics is not None:
        diagnostics.record(stage, diagnostics.current_segment, **counters)


def host_memory_snapshot():
    """Read bounded allocator metadata, not tensors or model weight contents.

    Comfy cudaHostRegister/HostBuffer allocations are separate from PyTorch's
    caching host allocator and glibc. Report each separately; never add them to
    RSS or assume registered bytes equal physical resident bytes.
    """
    mm = sys.modules.get('comfy.model_management')
    result = {'dynamic_models': [], 'errors': [], 'truncated': False}
    for name in ('TOTAL_PINNED_MEMORY', 'MAX_PINNED_MEMORY'):
        value = getattr(mm, name, None)
        if isinstance(value, (int, float)):
            result[name.lower()] = int(value)
    memory = sys.modules.get('comfy.memory_management')
    result['aimdo_enabled'] = getattr(memory, 'aimdo_enabled', None)
    for name in ('STREAM_CAST_BUFFERS', 'STREAM_AIMDO_CAST_BUFFERS', 'CROSS_STEP_STATE', 'DIRTY_MMAPS'):
        value = getattr(mm, name, None)
        if isinstance(value, (dict, list, tuple, set)):
            result[name.lower() + '_count'] = len(value)
    prefetch = sys.modules.get('comfy.model_prefetch')
    for name in ('PREFETCH_QUEUES', 'MALLOC_GRAPHS', 'GRAPH_CAPTURE_STREAMS'):
        value = getattr(prefetch, name, None)
        if isinstance(value, (dict, list, tuple)):
            result[name.lower() + '_count'] = len(value)
    seen = set()
    models = getattr(mm, 'current_loaded_models', ())
    if not isinstance(models, (list, tuple)):
        models = ()
    result['truncated'] = len(models) > 64
    for loaded in models[:64]:
        try:
            patcher = loaded.model
            model = getattr(patcher, 'model', None)
            states = getattr(model, 'dynamic_pins', None)
            if not isinstance(states, dict):
                continue
            state = states.get(getattr(patcher, 'load_device', None))
            if not isinstance(state, dict) or id(state) in seen:
                continue
            seen.add(id(state))
            row = {'model': type(model).__name__, 'device': str(patcher.load_device),
                   'active': bool(state.get('active')), 'subsets': {}}
            for subset in ('weights', 'weights-loaded', 'weights-fast', 'patches', 'patches-loaded', 'patches-fast'):
                entry = state.get(subset)
                if entry is None:
                    continue
                row['subsets'][subset] = {'host_buffer_bytes': int(entry[0].size),
                                          'registered_bytes': int(entry[3][0]),
                                          'stack_entries': len(entry[1])}
            result['dynamic_models'].append(row)
        except Exception as exc:
            result['errors'].append(type(exc).__name__)
    # Availability depends on torch version; never initialize CUDA for a probe.
    result['torch_host'] = None
    host_stats = getattr(getattr(torch.cuda, 'memory', None), 'host_memory_stats', None)
    if torch.cuda.is_initialized() and callable(host_stats):
        try:
            stats = host_stats()
            result['torch_host'] = {str(k): int(v) for k, v in stats.items()
                                    if isinstance(v, (int, float)) and
                                    (k.endswith('.current') or k in ('num_host_alloc', 'num_host_free'))}
        except Exception as exc:
            result['errors'].append('torch_host:' + type(exc).__name__)
    if result['dynamic_models']:
        for prefix in ('weights', 'patches'):
            for field in ('host_buffer_bytes', 'registered_bytes', 'stack_entries'):
                result[prefix + '_' + field] = sum(values[field]
                    for model in result['dynamic_models'] for subset, values in model['subsets'].items()
                    if subset.startswith(prefix))
    return result


class MemoryDiagnostics:
    def __init__(self, plan, root, *, rolling=False):
        setting = ((getattr(plan, 'raw', None) or {}).get('output') or {}).get('memoryDiagnostics', rolling)
        self.enabled = setting is True and os.getenv('CINESTACK_MEMORY_DIAGNOSTICS', '1') != '0'
        self.path = Path(root) / 'memory_diagnostics.jsonl' if root is not None else None
        self.run = uuid.uuid4().hex[:12]
        self.last = self.baseline = None
        self.current_segment = None
        self.segment_baseline = {}
        self.file_failed = False

    def record(self, stage, segment=None, groups=None, **counters):
        if not self.enabled:
            return
        try:
            self._record(stage, segment, groups or {}, counters)
        except Exception as exc:
            # Telemetry failures must not turn a successful generation into an error.
            log.warning('CineStack MEM diagnostic unavailable (%s)', type(exc).__name__)

    def _record(self, stage, segment, groups, counters):
        started = time.perf_counter()
        probe_errors = {}
        def probe(name, callback):
            try:
                return callback()
            except Exception as exc:
                probe_errors[name] = type(exc).__name__
                return None
        process = probe('process', process_snapshot) or {}
        rss = process.get('VmRSS')
        if self.baseline is None:
            self.baseline = rss
        if stage == 'segment_start':
            self.segment_baseline[segment] = rss
            self.current_segment = segment
        base = self.segment_baseline.get(segment)
        tensors = probe("tensors", lambda: storage_snapshot(groups)) if groups else None
        from ..package_version import PLUGIN_VERSION
        row = {'schema': 1, 'version': PLUGIN_VERSION, 'run': self.run, 'pid': os.getpid(),
               'time': time.time(), 'segment': segment, 'stage': stage, 'process': process,
               'delta_previous_rss': rss - self.last if rss is not None and self.last is not None else None,
               'delta_segment_rss': rss - base if rss is not None and base is not None else None,
               'delta_run_rss': rss - self.baseline if rss is not None and self.baseline is not None else None,
               'tensors': tensors, 'allocator': probe('allocator', allocator_snapshot),
               'cgroup': probe('cgroup', cgroup_snapshot), 'runtime': probe('runtime', runtime_snapshot),
               'host_memory': probe('host_memory', host_memory_snapshot),
               'counters': counters, 'probe_errors': probe_errors}
        self.last = rss
        row['diagnostic_ms'] = (time.perf_counter() - started) * 1000
        def mb(value):
            return 'n/a' if value is None else f'{value / MIB:.1f}'
        alloc = row['allocator'] or {}
        log.info('CineStack MEM: run=%s seg=%s stage=%s RSS=%s MiB delta=%s Anon=%s File=%s '
                 'tracked_cpu=%s heap_used=%s heap_free=%s malloc_mmap=%s models=%s '
                 'comfy_pinned=%s patch_host=%s patch_pinned=%s weight_pinned=%s',
                 self.run, segment, stage, mb(rss), mb(row['delta_previous_rss']),
                 mb(process.get('RssAnon')), mb(process.get('RssFile')), mb((tensors or {}).get('cpu_bytes')),
                 mb(alloc.get('uordblks')), mb(alloc.get('fordblks')), mb(alloc.get('hblkhd')),
                 (row['runtime'] or {}).get('loaded_model_records', 'n/a'),
                 mb((row['host_memory'] or {}).get('total_pinned_memory')),
                 mb((row['host_memory'] or {}).get('patches_host_buffer_bytes')),
                 mb((row['host_memory'] or {}).get('patches_registered_bytes')),
                 mb((row['host_memory'] or {}).get('weights_registered_bytes')))
        if self.path and not self.file_failed:
            try:
                with self.path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            except OSError:
                self.file_failed = True
                log.warning('CineStack MEM: cannot write diagnostics file; console observations continue.')
