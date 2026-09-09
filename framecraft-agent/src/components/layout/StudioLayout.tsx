import React from 'react';
import { Link } from 'react-router-dom';
import { Zap, Settings, Trash2, Sparkles, Play, FileJson, Layers } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';
import { useStudioWorkflow } from '../../hooks/useStudioWorkflow';
import { api } from '../../api/client';
import StepProgress from '../studio/StepProgress';
import DemoModeBanner from '../layout/DemoModeBanner';
import BottomStatusBar from '../layout/BottomStatusBar';
import AssetUploadZone from '../upload/AssetUploadZone';
import AssetCard from '../upload/AssetCard';
import AssetFilterTabs from '../upload/AssetFilterTabs';
import StudioEmptyState from '../studio/StudioEmptyState';
import AnalysisProgressPanel from '../studio/AnalysisProgressPanel';
import EditPlanCard from '../studio/EditPlanCard';
import VideoPreviewArea from '../studio/VideoPreviewArea';
import DownloadResultCard from '../studio/DownloadResultCard';
import MiniTimeline from '../studio/MiniTimeline';
import AgentChatPanel from '../agent/AgentChatPanel';
import ModelSettingsDrawer from '../settings/ModelSettingsDrawer';
import AssetDetailDrawer from '../asset/AssetDetailDrawer';
import ProjectSelector from '../layout/ProjectSelector';
import GradientButton from '../ui/GradientButton';

export default function StudioLayout() {
  const {
    step, assets, filter,
    clearProject, setShowSettingsDrawer,
    setSelectedAssetId, setShowAssetDrawer,
    generateHyperFramesProgress, generateDraftProgress,
    versions, currentVersionId, setCurrentVersionId, setPreviewUrl, setVersion, error,
    activeJobId, scriptText,
  } = useProjectStore();
  const { startAnalyze, saveScriptText } = useStudioWorkflow();

  const filteredAssets = filter === 'all' ? assets : assets.filter((a) => a.type === filter);
  const currentVersion = versions.find((v) => v.id === currentVersionId) || versions[0];

  const renderCenterPanel = () => {
    switch (step) {
      case 'upload':
        return (
          <div className="flex flex-col items-center gap-6 h-full justify-center">
            <StudioEmptyState />
            {(assets.length > 0 || scriptText.trim()) && (
              <GradientButton size="lg" className="rounded-xl px-8" onClick={() => void startAnalyze()} disabled={Boolean(activeJobId)}>
                <Play className="w-4 h-4" />
                {activeJobId ? 'Agent 任务运行中' : '开始 AI 分析'}
              </GradientButton>
            )}
          </div>
        );
      case 'analyze':
        return <AnalysisProgressPanel />;
      case 'plan':
        return <EditPlanCard />;
      case 'generate':
        return (
          <div className="flex flex-col gap-5 h-full justify-center">
            <div className="space-y-4">
              <div className="glass-card rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-text-main flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-primary-light" />
                    正在生成 HyperFrames 解说成片
                  </span>
                  <span className="text-xs text-primary-light font-mono">{generateHyperFramesProgress}%</span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-btn-gradient rounded-full transition-all duration-200" style={{ width: `${generateHyperFramesProgress}%` }} />
                </div>
              </div>
              <div className="glass-card rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold text-text-main flex items-center gap-2">
                    <Zap className="w-4 h-4 text-secondary" />
                    正在校验字幕、时间线与视觉细节
                  </span>
                  <span className="text-xs text-secondary font-mono">{Math.max(generateDraftProgress, Math.round(generateHyperFramesProgress * 0.9))}%</span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-secondary rounded-full transition-all duration-200" style={{ width: `${Math.max(generateDraftProgress, Math.round(generateHyperFramesProgress * 0.9))}%` }} />
                </div>
              </div>
            </div>
          </div>
        );
      case 'result':
        return (
          <div className="flex flex-col gap-4 h-full overflow-y-auto py-2">
            <div className="max-w-[280px] mx-auto">
              <VideoPreviewArea />
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-text-muted">版本：</span>
              {versions.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => {
                    setCurrentVersionId(v.id);
                    setVersion(`v${v.version_number}.0`);
                    if (v.preview_url) setPreviewUrl(api.fileUrl(v.preview_url));
                  }}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                    v.id === currentVersion?.id
                      ? 'bg-primary/15 text-primary-light border-primary/30'
                      : 'bg-white/4 text-text-muted border-white/8'
                  }`}
                >
                  v{v.version_number}.0
                </button>
              ))}
            </div>
            {currentVersion && (
              <div className="grid grid-cols-2 gap-3">
                {currentVersion.preview_url && (
                  <a href={api.fileUrl(currentVersion.preview_url)} download>
                    <DownloadResultCard title="完整视频" description="MP4 · HyperFrames 预览" icon={<Zap className="w-4 h-4 text-primary-light" />} badge="推荐" badgeVariant="primary" size="MP4" />
                  </a>
                )}
                {currentVersion.timeline_url && (
                  <a href={api.fileUrl(currentVersion.timeline_url)} download>
                    <DownloadResultCard title="项目时间线" description="timeline.json" icon={<FileJson className="w-4 h-4 text-accent" />} badge="JSON" badgeVariant="info" size="JSON" />
                  </a>
                )}
                {currentVersion.hyperframes_url && (
                  <a href={api.fileUrl(currentVersion.hyperframes_url)} download>
                    <DownloadResultCard title="HyperFrames 工程" description="HTML 成片工程 zip" icon={<Layers className="w-4 h-4 text-primary-light" />} badge="HF" badgeVariant="primary" size="ZIP" />
                  </a>
                )}
                {currentVersion.subtitles_url && (
                  <a href={api.fileUrl(currentVersion.subtitles_url)} download>
                    <DownloadResultCard title="字幕文件" description="SRT 格式" icon={<Zap className="w-4 h-4 text-warning" />} badge="可编辑" badgeVariant="info" size="SRT" />
                  </a>
                )}
                {currentVersion.cover_url && (
                  <a href={api.fileUrl(currentVersion.cover_url)} download>
                    <DownloadResultCard title="封面图" description="PNG 封面" icon={<Sparkles className="w-4 h-4 text-accent" />} badge="新生成" badgeVariant="warning" size="PNG" />
                  </a>
                )}
              </div>
            )}
            <MiniTimeline />
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg-main">
      <DemoModeBanner />
      {error && (
        <div className="px-6 py-2 bg-error/10 text-error text-xs border-b border-error/20">{error}</div>
      )}
      <div className="flex items-center justify-between px-6 py-3 border-b border-white/8 flex-shrink-0">
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-btn-gradient flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-bold text-text-main"><span className="gradient-text">FrameCraft</span> Agent</span>
          </Link>
        </div>
        <StepProgress />
        <div className="flex items-center gap-2">
          <ProjectSelector />
          <button type="button" onClick={() => setShowSettingsDrawer(true)} className="flex items-center gap-2 px-3 py-1.5 rounded-lg glass border border-white/10 text-xs text-text-secondary">
            <Settings className="w-3.5 h-3.5" /> 模型设置
          </button>
          <button type="button" onClick={clearProject} className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/8 text-xs text-text-muted hover:text-error">
            <Trash2 className="w-3.5 h-3.5" /> 清空项目
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <div className="w-[30%] border-r border-white/8 flex flex-col p-4 gap-4 overflow-hidden">
          <span className="text-sm font-bold text-text-main">输入与素材</span>
          <AssetUploadZone />
          <div className="glass-card rounded-xl p-3 border border-white/8">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-text-main">讲稿文字</span>
              <span className="text-[10px] text-text-muted">可选</span>
            </div>
            <textarea
              value={scriptText}
              onChange={(e) => void saveScriptText(e.target.value)}
              placeholder="没有音频时可直接贴讲稿；有音频时也可以补充文字要求。"
              className="w-full min-h-28 resize-y rounded-lg bg-white/5 border border-white/8 px-3 py-2 text-xs text-text-main placeholder:text-text-muted focus:outline-none focus:border-primary/40"
            />
          </div>
          <AssetFilterTabs />
          <div className="flex-1 overflow-y-auto space-y-2">
            {filteredAssets.map((asset) => (
              <AssetCard key={asset.id} asset={asset} onClick={() => { setSelectedAssetId(asset.id); setShowAssetDrawer(true); }} />
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-hidden p-5">{renderCenterPanel()}</div>
        <div className="w-[20%] border-l border-white/8 flex flex-col overflow-hidden">
          <AgentChatPanel />
        </div>
      </div>
      <BottomStatusBar />
      <ModelSettingsDrawer />
      <AssetDetailDrawer />
    </div>
  );
}
