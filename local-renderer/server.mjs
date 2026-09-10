import http from 'node:http';
import { createReadStream, createWriteStream, existsSync } from 'node:fs';
import { mkdir, readFile, rm, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import AdmZip from 'adm-zip';

const HOST = '127.0.0.1';
const PORT = Number(process.env.FRAMECRAFT_LOCAL_RENDERER_PORT || 19186);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RUNTIME = path.join(os.tmpdir(), 'framecraft-local-renderer');
const MAX_BUNDLE_BYTES = Number(process.env.FRAMECRAFT_LOCAL_RENDERER_MAX_BYTES || 350 * 1024 * 1024);
const JOB_TTL_MS = Number(process.env.FRAMECRAFT_LOCAL_RENDERER_TTL_MS || 60 * 60 * 1000);
const jobs = new Map();
let activeJobId = null;

const configuredOrigins = (process.env.FRAMECRAFT_LOCAL_RENDERER_ORIGINS || 'http://1.14.46.26')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);
const renderCrf = Math.max(18, Math.min(Number(process.env.FRAMECRAFT_LOCAL_RENDERER_CRF || 30), 40));

function originAllowed(origin) {
  if (!origin) return true;
  if (configuredOrigins.includes(origin)) return true;
  try {
    const parsed = new URL(origin);
    return ['localhost', '127.0.0.1'].includes(parsed.hostname);
  } catch {
    return false;
  }
}

function corsHeaders(req) {
  const origin = req.headers.origin;
  const headers = {
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Private-Network': 'true',
    'Cache-Control': 'no-store',
  };
  if (originAllowed(origin) && origin) headers['Access-Control-Allow-Origin'] = origin;
  return headers;
}

function sendJson(req, res, statusCode, payload) {
  res.writeHead(statusCode, { ...corsHeaders(req), 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

function publicJob(job) {
  return {
    id: job.id,
    status: job.status,
    progress: job.progress,
    step: job.step,
    error: job.error || null,
    created_at: job.createdAt,
    completed_at: job.completedAt || null,
    download_url: job.status === 'completed' ? `/jobs/${job.id}/video` : null,
    review_url: job.status === 'completed' ? `/jobs/${job.id}/review` : null,
    media_validation: job.mediaValidation || null,
  };
}

async function readRequestBody(req, target) {
  let size = 0;
  await new Promise((resolve, reject) => {
    const output = createWriteStream(target, { flags: 'wx' });
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BUNDLE_BYTES) {
        reject(new Error('HyperFrames 工程包超过本地 Renderer 大小限制。'));
        req.destroy();
        return;
      }
    });
    req.on('error', reject);
    output.on('error', reject);
    output.on('finish', resolve);
    req.pipe(output);
  });
  if (size === 0) throw new Error('收到的 HyperFrames 工程包为空。');
  return size;
}

function safeExtract(zipPath, destination) {
  const zip = new AdmZip(zipPath);
  const entries = zip.getEntries();
  if (entries.length > 5000) throw new Error('工程包文件数量超过本地 Renderer 限制。');
  let unpackedBytes = 0;
  for (const entry of entries) {
    const normalized = path.posix.normalize(entry.entryName.replaceAll('\\', '/'));
    if (normalized.startsWith('../') || normalized.startsWith('/') || normalized.includes('/../')) {
      throw new Error(`工程包包含不安全路径：${entry.entryName}`);
    }
    unpackedBytes += Number(entry.header?.size || 0);
    if (unpackedBytes > MAX_BUNDLE_BYTES * 4) throw new Error('工程包解压后体积超过本地 Renderer 限制。');
    const unixMode = Number(entry.header?.attr || 0) >>> 16;
    if ((unixMode & 0o170000) === 0o120000) throw new Error(`工程包不允许符号链接：${entry.entryName}`);
  }
  zip.extractAllTo(destination, true, false);
}

async function findHyperFramesDir(root) {
  const candidates = [root, path.join(root, 'hyperframes')];
  for (const candidate of candidates) {
    if (existsSync(path.join(candidate, 'index.html'))) return candidate;
  }
  throw new Error('工程包内未找到 HyperFrames index.html。');
}

async function run(command, args, options, onOutput) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { ...options, env: { ...process.env, HYPERFRAMES_NO_TELEMETRY: '1' } });
    let output = '';
    const receive = (chunk) => {
      const text = chunk.toString();
      output = (output + text).slice(-24000);
      onOutput?.(text);
    };
    child.stdout.on('data', receive);
    child.stderr.on('data', receive);
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) resolve(output);
      else reject(new Error(output.trim() || `${command} 退出码 ${code}`));
    });
  });
}

async function validateVideo(videoPath, expectedDuration) {
  const output = await run(
    'ffprobe',
    ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', videoPath],
    {},
  );
  const media = JSON.parse(output);
  const streams = media.streams || [];
  if (!streams.some((item) => item.codec_type === 'video') || !streams.some((item) => item.codec_type === 'audio')) {
    throw new Error('本地成片缺少视频流或音频流。');
  }
  const duration = Number(media.format?.duration || 0);
  if (!duration || Math.abs(duration - expectedDuration) > Math.max(0.8, expectedDuration * 0.02)) {
    throw new Error(`本地成片时长异常：期望 ${expectedDuration.toFixed(2)} 秒，实际 ${duration.toFixed(2)} 秒。`);
  }
  const video = streams.find((item) => item.codec_type === 'video');
  const info = await stat(videoPath);
  return {
    duration_s: duration,
    size_bytes: info.size,
    width: Number(video?.width || 0),
    height: Number(video?.height || 0),
    has_video: true,
    has_audio: true,
    renderer: 'hyperframes-strict',
  };
}

async function extractContactSheet(videoPath, outputPath, duration) {
  const interval = Math.max(duration / 8, 0.5);
  await run(
    'ffmpeg',
    ['-y', '-v', 'error', '-i', videoPath, '-vf', `fps=1/${interval},scale=480:-2,tile=4x2`, '-frames:v', '1', outputPath],
    {},
  );
}

async function render(job, fps) {
  activeJobId = job.id;
  try {
    job.status = 'running';
    job.progress = 5;
    job.step = '正在安全解压 HyperFrames 工程';
    const extracted = path.join(job.workspace, 'project');
    await mkdir(extracted, { recursive: true });
    safeExtract(job.bundlePath, extracted);
    const projectDir = await findHyperFramesDir(extracted);
    const manifest = JSON.parse(await readFile(path.join(projectDir, 'local-render-manifest.json'), 'utf8'));
    const renderFps = Math.max(15, Math.min(Number(fps || manifest.fps || 24), 60));
    const expectedDuration = Number(manifest.expected_duration_s || 0);
    if (!expectedDuration) throw new Error('本地渲染清单缺少有效时长。');
    job.progress = 12;
    job.step = '正在执行 HyperFrames 严格渲染';
    const cli = path.join(ROOT, 'node_modules', '.bin', process.platform === 'win32' ? 'hyperframes.cmd' : 'hyperframes');
    if (!existsSync(cli)) throw new Error('未安装 HyperFrames。请在 FrameCraft 目录运行 npm install。');
    await run(
      cli,
      [
        'render', '--output', job.videoPath, '--fps', String(renderFps),
        '--quality', 'standard', '--crf', String(renderCrf), '--strict',
      ],
      { cwd: projectDir, shell: process.platform === 'win32' },
      (text) => {
        const matches = [...text.matchAll(/(\d{1,3})%/g)];
        if (matches.length) job.progress = Math.min(92, 12 + Number(matches.at(-1)[1]) * 0.8);
      },
    );
    job.progress = 94;
    job.step = '正在检查本地成片完整性';
    job.mediaValidation = await validateVideo(job.videoPath, expectedDuration);
    job.reviewPath = path.join(job.workspace, 'contact-sheet.jpg');
    job.progress = 97;
    job.step = '正在生成本地视觉验收联系表';
    await extractContactSheet(job.videoPath, job.reviewPath, job.mediaValidation.duration_s);
    job.status = 'completed';
    job.progress = 100;
    job.step = '本地 HyperFrames 渲染完成';
    job.completedAt = new Date().toISOString();
  } catch (error) {
    job.status = 'failed';
    job.error = error instanceof Error ? error.message : String(error);
    job.step = '本地渲染未完成';
    job.completedAt = new Date().toISOString();
  } finally {
    activeJobId = null;
  }
}

async function handle(req, res) {
  if (!originAllowed(req.headers.origin)) return sendJson(req, res, 403, { error: '该网页来源未获本地 Renderer 授权。' });
  if (req.method === 'OPTIONS') {
    res.writeHead(204, corsHeaders(req));
    return res.end();
  }
  const url = new URL(req.url || '/', `http://${HOST}:${PORT}`);
  if (req.method === 'GET' && url.pathname === '/health') {
    return sendJson(req, res, 200, {
      ok: true,
      service: 'framecraft-local-renderer',
      busy: Boolean(activeJobId),
      active_job_id: activeJobId,
    });
  }
  if (req.method === 'POST' && url.pathname === '/render') {
    if (activeJobId) return sendJson(req, res, 409, { error: '本地 Renderer 已有任务在运行。' });
    if (req.headers['content-type'] !== 'application/zip') {
      return sendJson(req, res, 415, { error: '请求必须是 application/zip。' });
    }
    const id = randomUUID();
    const workspace = path.join(RUNTIME, id);
    await mkdir(workspace, { recursive: true });
    const job = {
      id,
      workspace,
      bundlePath: path.join(workspace, 'hyperframes.zip'),
      videoPath: path.join(workspace, 'preview.mp4'),
      status: 'queued',
      progress: 0,
      step: '正在接收 HyperFrames 工程',
      createdAt: new Date().toISOString(),
    };
    jobs.set(id, job);
    activeJobId = id;
    try {
      await readRequestBody(req, job.bundlePath);
    } catch (error) {
      jobs.delete(id);
      activeJobId = null;
      await rm(workspace, { recursive: true, force: true });
      return sendJson(req, res, 400, { error: error instanceof Error ? error.message : String(error) });
    }
    void render(job, Number(url.searchParams.get('fps') || 24));
    return sendJson(req, res, 202, publicJob(job));
  }
  const jobMatch = url.pathname.match(/^\/jobs\/([0-9a-f-]+)$/i);
  if (req.method === 'GET' && jobMatch) {
    const job = jobs.get(jobMatch[1]);
    return job ? sendJson(req, res, 200, publicJob(job)) : sendJson(req, res, 404, { error: '本地渲染任务不存在。' });
  }
  const videoMatch = url.pathname.match(/^\/jobs\/([0-9a-f-]+)\/video$/i);
  if (req.method === 'GET' && videoMatch) {
    const job = jobs.get(videoMatch[1]);
    if (!job || job.status !== 'completed') return sendJson(req, res, 404, { error: '本地成片尚未生成。' });
    const info = await stat(job.videoPath);
    res.writeHead(200, {
      ...corsHeaders(req),
      'Content-Type': 'video/mp4',
      'Content-Length': info.size,
      'Content-Disposition': `attachment; filename="framecraft-${job.id}.mp4"`,
    });
    return createReadStream(job.videoPath).pipe(res);
  }
  const reviewMatch = url.pathname.match(/^\/jobs\/([0-9a-f-]+)\/review$/i);
  if (req.method === 'GET' && reviewMatch) {
    const job = jobs.get(reviewMatch[1]);
    if (!job || job.status !== 'completed') return sendJson(req, res, 404, { error: '本地视觉验收联系表尚未生成。' });
    const info = await stat(job.reviewPath);
    res.writeHead(200, {
      ...corsHeaders(req),
      'Content-Type': 'image/jpeg',
      'Content-Length': info.size,
      'Cache-Control': 'no-store',
    });
    return createReadStream(job.reviewPath).pipe(res);
  }
  return sendJson(req, res, 404, { error: '接口不存在。' });
}

await mkdir(RUNTIME, { recursive: true });
setInterval(async () => {
  const cutoff = Date.now() - JOB_TTL_MS;
  for (const [id, job] of jobs.entries()) {
    if (job.status !== 'running' && Date.parse(job.createdAt) < cutoff) {
      jobs.delete(id);
      await rm(job.workspace, { recursive: true, force: true });
    }
  }
}, 60_000).unref();

http.createServer((req, res) => {
  void handle(req, res).catch((error) => sendJson(req, res, 500, { error: error instanceof Error ? error.message : String(error) }));
}).listen(PORT, HOST, () => {
  console.log(`[FrameCraft Renderer] http://${HOST}:${PORT}`);
  console.log(`[FrameCraft Renderer] allowed origins: ${configuredOrigins.join(', ')}, localhost`);
});
