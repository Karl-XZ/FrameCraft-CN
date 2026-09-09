import React from 'react';
import { LayoutTemplate } from 'lucide-react';
import GlassCard from '../ui/GlassCard';

/** 落地页工作台入口预览，不展示伪造任务进度或文件名。 */
export default function DemoPreviewCard() {
  return (
    <GlassCard className="p-5 flex flex-col gap-4 animate-float">
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">工作台入口预览</span>
        <div className="flex items-center gap-1">
          <LayoutTemplate className="w-3 h-3 text-info" />
          <span className="text-xs text-info">真实生成流程</span>
        </div>
      </div>

      <div className="relative rounded-lg overflow-hidden bg-black/50 aspect-video flex items-center justify-center border border-dashed border-white/10">
        <p className="text-xs text-text-muted px-4 text-center">
          上传素材并由 Agent 分析后，此处显示 HyperFrames 预览成片
        </p>
      </div>

      <div className="space-y-2 text-xs text-text-muted">
        <p>· Agent 分析音频或讲稿并生成视频方案</p>
        <p>· HyperFrames 真实渲染 faceless explainer 成片</p>
        <p>· 保留可继续修改的 HyperFrames 源工程</p>
      </div>
    </GlassCard>
  );
}
