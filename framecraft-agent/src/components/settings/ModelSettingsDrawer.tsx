import React, { useEffect, useMemo, useState } from 'react';
import { X, Shield, Monitor, Zap } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';
import { api } from '../../api/client';

const RATIOS = ['9:16', '16:9', '1:1'];
const RESOLUTIONS = ['720p快速预览', '1080p正式导出', '4K旗舰版'];
const DRAFT_TARGETS = ['不导出草稿'];

type ProviderOption = { id: string; label: string; base_url: string };

const PROVIDER_DEFAULTS: Record<string, { text_model: string; vision_model: string }> = {
  deepseek: { text_model: 'deepseek-v4-flash', vision_model: 'deepseek-v4-flash-vision-exp' },
};

export default function ModelSettingsDrawer() {
  const {
    showSettingsDrawer, setShowSettingsDrawer,
    setModelProvider,
    apiKey, setApiKey,
    videoRatio, setVideoRatio,
    videoResolution, setVideoResolution,
    frameRate, setFrameRate,
    targetDuration, setTargetDuration,
    draftTarget, setDraftTarget,
  } = useProjectStore();

  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [textModel, setTextModel] = useState('deepseek-v4-flash');
  const [visionModel, setVisionModel] = useState('deepseek-v4-flash-vision-exp');
  const [baseUrl, setBaseUrl] = useState('https://api.deepseek.com');
  const [providerId, setProviderId] = useState('deepseek');
  const [ttsModel, setTtsModel] = useState('edge-tts');
  const [ttsVoice, setTtsVoice] = useState('zh-CN-XiaoxiaoNeural');

  useEffect(() => {
    if (!showSettingsDrawer) return;
    void Promise.all([api.getSettings(), api.getModelProviders()]).then(([s, meta]) => {
      const list = ((meta.providers as ProviderOption[] | undefined) || Object.entries(meta)
        .filter(([id, value]) => id !== 'providers' && typeof value === 'object' && value)
        .map(([id, value]) => ({
          id,
          label: String((value as Record<string, unknown>).label || id),
          base_url: String((value as Record<string, unknown>).base_url || ''),
        })));
      setProviders(list);
      const pid = (s.provider as string) || 'deepseek';
      setProviderId(pid);
      const match = list.find((p) => p.id === pid);
      setModelProvider(match?.label || pid);
      if (s.api_key) setApiKey(s.api_key);
      if (s.text_model) setTextModel(s.text_model);
      if (s.vision_model) setVisionModel(s.vision_model);
      if (s.tts_model) setTtsModel(s.tts_model);
      if (s.tts_voice) setTtsVoice(s.tts_voice);
      if (s.base_url) setBaseUrl(s.base_url);
      else if (match?.base_url) setBaseUrl(match.base_url);
    });
  }, [showSettingsDrawer, setApiKey, setModelProvider]);

  const providerButtons = useMemo(
    () => (providers.length ? providers : [
      { id: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com' },
    ]),
    [providers],
  );

  const selectProvider = (p: ProviderOption) => {
    setProviderId(p.id);
    setModelProvider(p.label);
    setBaseUrl(p.base_url);
    const defaults = PROVIDER_DEFAULTS[p.id];
    if (defaults) {
      setTextModel(defaults.text_model);
      setVisionModel(defaults.vision_model);
    }
  };

  const save = async () => {
    await api.saveSettings({
      provider: providerId,
      api_key: apiKey,
      text_model: textModel,
      vision_model: visionModel,
      asr_model: 'whisper-small',
      tts_model: ttsModel,
      tts_voice: ttsVoice,
      base_url: baseUrl,
    });
    setShowSettingsDrawer(false);
  };

  if (!showSettingsDrawer) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => setShowSettingsDrawer(false)}
      />

      <div className="relative ml-auto w-[480px] h-full glass-strong border-l border-white/10 flex flex-col animate-slide-in-right overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/8">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
              <Monitor className="w-4 h-4 text-primary-light" />
            </div>
            <span className="text-base font-bold text-text-main">模型设置</span>
          </div>
          <button
            onClick={() => setShowSettingsDrawer(false)}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4 text-text-muted" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-primary-light" />
              模型提供商
            </label>
            <div className="grid grid-cols-2 gap-2">
              {providerButtons.map((p) => (
                <button
                  key={p.id}
                  onClick={() => selectProvider(p)}
                  className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
                    providerId === p.id
                      ? 'bg-primary/15 text-primary-light border-primary/30'
                      : 'bg-white/4 text-text-secondary border-white/8 hover:border-white/15'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main">API Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/8 text-xs text-text-main font-mono focus:outline-none focus:border-primary/40"
            />
            <p className="text-xs text-text-muted">
              后端通过 openJiuwen 多 Agent 团队调用 DeepSeek OpenAI 兼容接口。默认地址为 `https://api.deepseek.com`。
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-xs text-text-muted">文本模型</label>
              <input
                value={textModel}
                onChange={(e) => setTextModel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main focus:outline-none focus:border-primary/40"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-text-muted">视觉模型</label>
              <input
                value={visionModel}
                onChange={(e) => setVisionModel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main focus:outline-none focus:border-primary/40"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-xs text-text-muted">TTS 模型</label>
              <input
                value={ttsModel}
                onChange={(e) => setTtsModel(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main focus:outline-none focus:border-primary/40"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-text-muted">TTS 音色</label>
              <input
                value={ttsVoice}
                onChange={(e) => setTtsVoice(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main focus:outline-none focus:border-primary/40"
              />
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-warning" />
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main placeholder:text-text-muted focus:outline-none focus:border-primary/40 transition-all"
            />
            <div className="flex items-start gap-2 p-3 rounded-lg bg-warning/10 border border-warning/15">
              <Shield className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />
              <p className="text-xs text-warning/90 leading-relaxed">
              API Key 只保存在后端，前端不会回显。默认使用 V4 Flash 并行规划、V4 Pro 汇总设计、V4 Flash Vision 验收成片。
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main">视频输出设置</label>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-text-muted mb-2">画面比例</p>
                <div className="flex gap-2">
                  {RATIOS.map((r) => (
                    <button
                      key={r}
                      onClick={() => setVideoRatio(r)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${
                        videoRatio === r
                          ? 'bg-primary/15 text-primary-light border-primary/30'
                          : 'bg-white/4 text-text-secondary border-white/8'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-text-muted mb-2">分辨率</p>
                <div className="flex gap-2">
                  {RESOLUTIONS.map((r) => (
                    <button
                      key={r}
                      onClick={() => setVideoResolution(r)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${
                        videoResolution === r
                          ? 'bg-primary/15 text-primary-light border-primary/30'
                          : 'bg-white/4 text-text-secondary border-white/8'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <p className="text-xs text-text-muted">帧率</p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setFrameRate(Math.max(24, frameRate - 1))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    -
                  </button>
                  <span className="text-sm font-mono text-text-main w-12 text-center">{frameRate} fps</span>
                  <button
                    onClick={() => setFrameRate(Math.min(60, frameRate + 1))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    +
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <p className="text-xs text-text-muted">目标时长</p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setTargetDuration(Math.max(15, targetDuration - 5))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    -
                  </button>
                  <span className="text-sm font-mono text-text-main w-12 text-center">{targetDuration}s</span>
                  <button
                    onClick={() => setTargetDuration(Math.min(300, targetDuration + 5))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main">工程导出策略</label>
            <div className="space-y-2">
              {DRAFT_TARGETS.map((t) => (
                <button
                  key={t}
                  onClick={() => setDraftTarget(t)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border transition-all text-left ${
                    draftTarget === t
                      ? 'bg-primary/10 border-primary/25 text-primary-light'
                      : 'bg-white/4 border-white/8 text-text-secondary hover:border-white/15'
                  }`}
                >
                  <div className={`w-3 h-3 rounded-full border-2 ${
                    draftTarget === t ? 'border-primary-light bg-primary-light' : 'border-white/20'
                  }`} />
                  <div>
                    <p className="text-sm font-medium">{t}</p>
                    <p className="text-xs text-text-muted mt-0.5">
                      当前版本只保留 HyperFrames 源工程和最终 MP4，不同步生成剪映草稿。
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-white/8">
          <button type="button" onClick={() => void save()} className="gradient-btn w-full py-3 rounded-xl text-sm font-semibold">
            保存设置
          </button>
        </div>
      </div>
    </div>
  );
}
