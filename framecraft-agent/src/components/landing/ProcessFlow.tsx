import React from 'react';
import { Upload, Brain, Scissors, Eye, Download } from 'lucide-react';

const STEPS = [
  { icon: <Upload className="w-5 h-5" />, label: '上传音频 / 讲稿', color: 'bg-primary/15 text-primary-light' },
  { icon: <Brain className="w-5 h-5" />, label: '内容分析', color: 'bg-secondary/15 text-secondary' },
  { icon: <Scissors className="w-5 h-5" />, label: 'Agent 设计分镜', color: 'bg-accent/15 text-accent' },
  { icon: <Eye className="w-5 h-5" />, label: 'HyperFrames 渲染', color: 'bg-warning/15 text-warning' },
  { icon: <Download className="w-5 h-5" />, label: '导出成片与工程', color: 'bg-success/15 text-success' },
];

export default function ProcessFlow() {
  return (
    <div className="flex items-center justify-center gap-3 flex-wrap">
      {STEPS.map((step, idx) => (
        <React.Fragment key={idx}>
          <div className="flex flex-col items-center gap-2">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${step.color}`}>
              {step.icon}
            </div>
            <span className="text-xs text-text-secondary font-medium">{step.label}</span>
          </div>
          {idx < STEPS.length - 1 && (
            <div className="flex items-center gap-1 mt-[-20px]">
              <div className="w-8 h-px bg-gradient-to-r from-primary/40 to-secondary/40" />
              <div className="w-1.5 h-1.5 rounded-full bg-primary/40" />
              <div className="w-8 h-px bg-gradient-to-r from-secondary/40 to-accent/40" />
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
