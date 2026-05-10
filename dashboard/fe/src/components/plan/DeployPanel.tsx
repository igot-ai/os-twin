'use client';

import { usePlanContext } from './PlanWorkspace';
import { useDeployStatus } from '@/hooks/use-deploy';
import { LaunchResponse } from '@/types';

interface DeployPanelProps {
  launchResult: LaunchResponse | null;
  onClose?: () => void;
}

export default function DeployPanel({ launchResult, onClose }: DeployPanelProps) {
  const { planId } = usePlanContext();
  const { 
    deployStatus, 
    isLoading, 
    startPreview, 
    stopPreview, 
    restartPreview 
  } = useDeployStatus(planId);

  const runtimeSanity = launchResult?.runtime_sanity;
  const warnings = runtimeSanity?.warnings ?? [];
  const errors = runtimeSanity?.errors ?? [];
  const hasWarnings = warnings.length > 0;
  const hasErrors = errors.length > 0;

  if (!launchResult && !deployStatus) {
    return null;
  }

  const workingDir = launchResult?.working_dir ?? deployStatus?.working_dir;
  const launchLog = launchResult?.launch_log;
  const localUrl = deployStatus?.local_url;
  const publicUrl = deployStatus?.public_url;
  const previewLog = deployStatus?.log_file;
  const isRunning = deployStatus?.status === 'running';
  const isNotConfigured = deployStatus?.status === 'not_configured';
  const command = deployStatus?.command;

  return (
    <div className="border-t border-border bg-surface-alt">
      {/* Header */}
      <div className="px-3 py-2 flex items-center justify-between border-b border-border">
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[16px] text-primary">
            {isRunning ? 'play_circle' : hasErrors ? 'error' : hasWarnings ? 'warning' : 'rocket_launch'}
          </span>
          <span className="text-xs font-bold text-text-main">Deploy</span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-main transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        )}
      </div>

      {/* Content */}
      <div className="p-3 space-y-3">
        {/* Status Badge */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Preview Status
          </span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
            isRunning 
              ? 'bg-emerald-100 text-emerald-700' 
              : isNotConfigured
              ? 'bg-gray-100 text-gray-600'
              : 'bg-amber-100 text-amber-700'
          }`}>
            {isLoading ? 'Loading...' : isRunning ? 'Running' : isNotConfigured ? 'Not Configured' : 'Stopped'}
          </span>
        </div>

        {/* Working Dir */}
        {workingDir && (
          <div className="space-y-0.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Working Dir
            </span>
            <p className="text-[11px] text-text-main font-mono truncate" title={workingDir}>
              {workingDir}
            </p>
          </div>
        )}

        {/* Launch Log */}
        {launchLog && (
          <div className="space-y-0.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Launch Log
            </span>
            <p className="text-[11px] text-text-muted font-mono truncate" title={launchLog}>
              {launchLog}
            </p>
          </div>
        )}

        {/* Preview Command */}
        {command && (
          <div className="space-y-0.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Command
            </span>
            <p className="text-[11px] text-text-main font-mono truncate" title={command}>
              {command}
            </p>
          </div>
        )}

        {/* URLs */}
        {(localUrl || publicUrl) && (
          <div className="space-y-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              URLs
            </span>
            <div className="flex flex-col gap-1">
              {localUrl && (
                <a
                  href={localUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-primary hover:underline font-mono flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-[12px]">open_in_new</span>
                  Local: {localUrl}
                </a>
              )}
              {publicUrl && (
                <a
                  href={publicUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-primary hover:underline font-mono flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-[12px]">public</span>
                  Public: {publicUrl}
                </a>
              )}
            </div>
          </div>
        )}

        {/* Warnings */}
        {hasWarnings && (
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px] text-amber-500">warning</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600">
                Warnings
              </span>
            </div>
            <ul className="text-[10px] text-text-muted space-y-0.5 pl-1">
              {warnings.map((w, i) => (
                <li key={i} className="truncate" title={w}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Errors */}
        {hasErrors && (
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px] text-red-500">error</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-red-600">
                Errors
              </span>
            </div>
            <ul className="text-[10px] text-text-muted space-y-0.5 pl-1">
              {errors.map((e, i) => (
                <li key={i} className="truncate" title={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Preview Log */}
        {previewLog && (
          <div className="space-y-0.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Preview Log
            </span>
            <p className="text-[11px] text-text-muted font-mono truncate" title={previewLog}>
              {previewLog}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-1.5 pt-1">
          {!isRunning ? (
            <button
              onClick={() => startPreview()}
              disabled={isLoading || isNotConfigured}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded text-[10px] font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[14px]">play_arrow</span>
              Start Preview
            </button>
          ) : (
            <button
              onClick={() => stopPreview()}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded text-[10px] font-semibold bg-red-600 text-white hover:bg-red-700 transition-all disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[14px]">stop</span>
              Stop Preview
            </button>
          )}
          {isRunning && (
            <button
              onClick={() => restartPreview()}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded text-[10px] font-semibold bg-primary/10 text-primary hover:bg-primary/20 transition-all disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[14px]">refresh</span>
              Restart
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
