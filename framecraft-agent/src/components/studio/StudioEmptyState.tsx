import React from 'react';
import { Upload, Zap } from 'lucide-react';
import GradientButton from '../ui/GradientButton';

export default function StudioEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-8">
      {/* Icon */}
      <div className="w-20 h-20 rounded-3xl bg-btn-gradient/20 flex items-center justify-center animate-float">
        <Zap className="w-10 h-10 text-primary-light" />
      </div>

      <div className="text-center space-y-3">
        <h2 className="text-2xl font-extrabold text-text-main tracking-tight">
          开始创建你的 AI 解说视频
        </h2>
        <p className="text-sm text-text-muted max-w-sm mx-auto leading-relaxed">
          上传解说音频，或先写讲稿文字。Agent 完成分镜、动画与字幕后，由用户电脑执行 HyperFrames 真实渲染
        </p>
      </div>

      <div className="flex items-center gap-4">
        <GradientButton size="lg" className="rounded-xl px-8 py-4">
          <Upload className="w-4 h-4" />
          上传素材
        </GradientButton>
      </div>

      {/* Supported formats */}
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <span>支持格式：</span>
        {['MP4', 'MOV', 'MP3', 'WAV', 'JPG', 'PNG'].map((f) => (
          <span key={f} className="px-1.5 py-0.5 rounded bg-white/5 border border-white/8 text-text-muted">
            {f}
          </span>
        ))}
      </div>
    </div>
  );
}
