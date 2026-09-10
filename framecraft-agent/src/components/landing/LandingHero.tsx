import React from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, Play } from 'lucide-react';
import DemoPreviewCard from './DemoPreviewCard';
import FeatureCard from './FeatureCard';
import ProcessFlow from './ProcessFlow';
import { Brain, Film, Download, MessageCircle, Zap } from 'lucide-react';
import GradientButton from '../ui/GradientButton';

export default function LandingHero() {
  return (
    <div className="min-h-screen flex flex-col bg-bg-main relative overflow-x-hidden">
      {/* Background orbs */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-[600px] h-[600px] rounded-full animate-orb-1"
          style={{ background: 'radial-gradient(circle, rgba(124,58,237,0.35), transparent 30%)' }} />
        <div className="absolute top-0 right-0 w-[700px] h-[700px] rounded-full animate-orb-2"
          style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.25), transparent 35%)' }} />
        <div className="absolute bottom-0 left-1/2 w-[800px] h-[800px] rounded-full animate-orb-3"
          style={{ background: 'radial-gradient(circle, rgba(244,114,182,0.18), transparent 40%)' }} />
      </div>

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-btn-gradient flex items-center justify-center shadow-glow">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-2xl font-extrabold tracking-tight">
            <span className="gradient-text">FrameCraft</span>
            <span className="text-text-main"> Agent</span>
          </span>
        </div>
        <div className="flex items-center gap-3">
          {['openJiuwen', 'DeepSeek V4', 'HyperFrames'].map((badge) => (
            <span key={badge} className="px-3 py-1 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-text-secondary">
              {badge}
            </span>
          ))}
          <Link
            to="/projects"
            className="ml-2 px-4 py-1.5 rounded-full text-xs font-semibold bg-white/5 border border-white/10 text-text-secondary hover:text-text-main hover:bg-white/[0.08] transition-colors"
          >
            项目列表
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <main className="relative z-10 flex-1 flex flex-col px-8 py-10 max-w-screen-xl mx-auto w-full gap-16">
        {/* Hero split */}
        <div className="flex items-center gap-16 min-h-[380px]">
          {/* Left */}
          <div className="flex-1 space-y-8 animate-fade-in-up">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-xs text-primary-light font-medium">
                <Sparkles className="w-3.5 h-3.5" />
                AI 驱动的解说视频生成引擎
              </div>
            </div>
            <h1 className="text-5xl font-extrabold leading-tight tracking-tight" style={{ letterSpacing: '-0.02em' }}>
              <span className="text-text-main">让音频或讲稿</span>
              <br />
              <span className="gradient-text">从输入到成片</span>
              <br />
              <span className="text-text-secondary">一步进入 HyperFrames 解说工作流</span>
            </h1>
            <p className="text-lg text-text-secondary max-w-md leading-relaxed">
              上传解说音频，或直接粘贴讲稿文字。云端 Agent 自动完成设计，HyperFrames 在用户电脑真实渲染，素材与算力更可控。
            </p>
            <div className="flex items-center gap-4">
              <Link
                to="/studio"
                className="gradient-btn px-7 py-3.5 rounded-xl text-base font-bold flex items-center gap-2 shadow-glow"
              >
                <Zap className="w-4 h-4" />
                开始生成视频
              </Link>
              <Link
                to="/studio"
                className="flex items-center gap-2 px-5 py-3.5 rounded-xl text-base font-semibold glass hover:bg-white/[0.08] transition-colors text-text-secondary hover:text-text-main border border-white/10"
              >
                <Play className="w-4 h-4" />
                查看演示流程
              </Link>
            </div>
          </div>

          {/* Right: Demo preview */}
          <div className="w-[420px] flex-shrink-0 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            <DemoPreviewCard />
          </div>
        </div>

        {/* Features */}
        <div className="space-y-6">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-text-main">为什么选择 FrameCraft Agent</h2>
            <p className="text-sm text-text-muted mt-2">一站式 faceless explainer 解说生成方案</p>
          </div>
          <div className="grid grid-cols-4 gap-4">
            <FeatureCard
              title="理解音频与讲稿"
              description="自动转写内容、整理结构并生成场景种子，不需要手工先做时间线"
              icon={<Brain className="w-5 h-5 text-primary-light" />}
              gradient="bg-primary/15 text-primary-light"
            />
            <FeatureCard
              title="HyperFrames 高级生成"
              description="云端生成可复现的 HTML 动画工程，用户电脑负责真实渲染最终成片"
              icon={<Film className="w-5 h-5 text-secondary" />}
              gradient="bg-secondary/15 text-secondary"
            />
            <FeatureCard
              title="保留项目工程"
              description="输出 MP4 的同时保留 HyperFrames 源工程，便于继续修改和再渲染"
              icon={<Download className="w-5 h-5 text-accent" />}
              gradient="bg-accent/15 text-accent"
            />
            <FeatureCard
              title="对话式继续修改"
              description="用自然语言指挥 AI 修改任何细节，无需手动操作时间线"
              icon={<MessageCircle className="w-5 h-5 text-warning" />}
              gradient="bg-warning/15 text-warning"
            />
          </div>
        </div>

        {/* Process */}
        <div className="space-y-8 py-8">
          <div className="text-center space-y-2">
            <h2 className="text-2xl font-bold text-text-main">工作流程</h2>
            <p className="text-sm text-text-muted">从上传到导出，五步完成专业级解说视频</p>
          </div>
          <ProcessFlow />
        </div>

        {/* Bottom CTA */}
        <div className="text-center space-y-6 pb-12">
          <GradientButton size="lg" className="px-12 py-4 text-lg rounded-2xl shadow-glow animate-pulse-glow">
            <Zap className="w-5 h-5" />
            立即进入工作台
          </GradientButton>
          <p className="text-xs text-text-muted">无需配置 · 上传即用 · 完全免费体验</p>
        </div>
      </main>
    </div>
  );
}
