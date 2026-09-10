const LOCAL_RENDERER_BASE = import.meta.env.VITE_LOCAL_RENDERER_URL ?? 'http://127.0.0.1:19186';

interface LocalRenderJob {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  step: string;
  error: string | null;
  download_url: string | null;
  review_url: string | null;
  media_validation: Record<string, unknown> | null;
}

function loopbackRequest(options?: RequestInit): RequestInit {
  return {
    ...options,
    // Chrome 142+ requires a public HTTPS page to declare loopback access before
    // it can show the user the Local Network Access permission prompt.
    targetAddressSpace: 'loopback',
  } as RequestInit;
}

function localRendererHelp(error: unknown) {
  const hostname = window.location.hostname;
  if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(hostname)) {
    return new Error('本地渲染需要通过 HTTPS 打开 FrameCraft；当前页面不是安全连接。', { cause: error });
  }
  return new Error(
    '无法连接本地 Renderer。请先启动 FrameCraft Renderer；如果浏览器询问本地网络访问，请选择“允许”。曾拒绝过时，请点击地址栏左侧的站点图标，在“网站设置”中允许本地网络访问后重试。',
    { cause: error },
  );
}

async function localRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${LOCAL_RENDERER_BASE}${path}`, loopbackRequest(options));
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
    throw localRendererHelp(error);
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function renderLocally(
  bundle: Blob,
  fps: number,
  onProgress: (progress: number, step: string) => void,
): Promise<{ video: Blob; contactSheet: Blob; mediaValidation: Record<string, unknown> }> {
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
  const [videoResponse, reviewResponse] = await Promise.all([
    fetch(`${LOCAL_RENDERER_BASE}/jobs/${started.id}/video`, loopbackRequest()),
    fetch(`${LOCAL_RENDERER_BASE}/jobs/${started.id}/review`, loopbackRequest()),
  ]);
  if (!videoResponse.ok) throw new Error('本地成片读取失败。');
  if (!reviewResponse.ok) throw new Error('本地视觉验收联系表读取失败。');
  return {
    video: await videoResponse.blob(),
    contactSheet: await reviewResponse.blob(),
    mediaValidation: job.media_validation || {},
  };
}
