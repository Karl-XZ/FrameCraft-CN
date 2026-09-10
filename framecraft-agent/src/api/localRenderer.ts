const LOCAL_RENDERER_BASE = import.meta.env.VITE_LOCAL_RENDERER_URL ?? 'http://127.0.0.1:19186';

interface LocalRenderJob {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  step: string;
  error: string | null;
  download_url: string | null;
}

async function localRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${LOCAL_RENDERER_BASE}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(body.error || `本地 Renderer 请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export async function checkLocalRenderer() {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 2500);
  try {
    return await localRequest<{ ok: boolean; busy: boolean }>('/health', { signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('没有检测到本地 Renderer，请先在用户电脑启动 FrameCraft Renderer。', { cause: error });
    }
    throw new Error('没有检测到本地 Renderer，请先在用户电脑启动 FrameCraft Renderer。', { cause: error });
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function renderLocally(
  bundle: Blob,
  fps: number,
  onProgress: (progress: number, step: string) => void,
): Promise<Blob> {
  const health = await checkLocalRenderer();
  if (health.busy) throw new Error('本地 Renderer 正在处理另一个视频，请稍后重试。');
  const started = await localRequest<LocalRenderJob>(`/render?fps=${encodeURIComponent(fps)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/zip' },
    body: bundle,
  });
  const deadline = Date.now() + 45 * 60 * 1000;
  let job = started;
  while (!['completed', 'failed'].includes(job.status)) {
    if (Date.now() > deadline) throw new Error('本地 HyperFrames 渲染超过 45 分钟。');
    onProgress(Math.round(job.progress || 0), job.step || '正在本地渲染');
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    job = await localRequest<LocalRenderJob>(`/jobs/${started.id}`);
  }
  if (job.status === 'failed') throw new Error(job.error || '本地 HyperFrames 渲染未完成。');
  onProgress(100, job.step || '本地渲染完成');
  const response = await fetch(`${LOCAL_RENDERER_BASE}/jobs/${started.id}/video`);
  if (!response.ok) throw new Error('本地成片读取失败。');
  return response.blob();
}
