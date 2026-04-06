'use client';

import { useState, useEffect } from 'react';
import { Connector, ConnectorInstance } from '@/types';
import { useConnectorInstances, useConnectorInstance } from '@/hooks/use-connectors';
import { apiGet } from '@/lib/api-client';
import { motion, AnimatePresence } from 'framer-motion';
import DocumentBrowser from './DocumentBrowser';

interface ConnectorSetupPanelProps {
  instance?: ConnectorInstance;
  connector?: Connector;
  isOpen: boolean;
  onClose: () => void;
}

enum SetupStep {
  Authenticate = 0,
  Configure = 1,
}

export default function ConnectorSetupPanel({ instance, connector, isOpen, onClose }: ConnectorSetupPanelProps) {
  const { createInstance } = useConnectorInstances();
  const { updateInstance, validateInstance, deleteInstance } = useConnectorInstance(instance?.id || null);
  
  const [step, setStep] = useState<SetupStep>(SetupStep.Authenticate);
  const [name, setName] = useState('');
  const [config, setConfig] = useState<Record<string, any>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{ status: string; message?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isAuthed, setIsAuthed] = useState(false);
  const [showDocBrowser, setShowDocBrowser] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setName(instance?.name || connector?.name || '');
      setConfig(instance?.config || {});
      setValidationResult(null);
      setError(null);
      
      const isOAuth = connector?.authConfig.mode === 'oauth';
      if (instance || !isOAuth) {
        setStep(SetupStep.Configure);
        setIsAuthed(true);
      } else {
        setStep(SetupStep.Authenticate);
        setIsAuthed(false);
      }
    }
  }, [isOpen, instance, connector]);

  const handleStartOAuth = () => {
    const provider = connector?.authConfig.mode === 'oauth' ? connector.authConfig.provider : null;
    if (!provider) return;
    
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    
    const popup = window.open(
      `/api/oauth/authorize/${provider}`,
      'OAuth Login',
      `width=${width},height=${height},left=${left},top=${top}`
    );
    
    const interval = setInterval(async () => {
       if (popup?.closed) {
          clearInterval(interval);
       }
       try {
         const status = await apiGet<{ authenticated: boolean }>(`/oauth/status/${provider}`);
         if (status.authenticated) {
            clearInterval(interval);
            popup?.close();
            setIsAuthed(true);
            setStep(SetupStep.Configure);
         }
       } catch (err) {
         console.error('Failed to check OAuth status', err);
       }
    }, 2000);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      if (instance) {
        await updateInstance({ name, config });
      } else if (connector) {
        await createInstance({ 
          connector_id: connector.id, 
          name, 
          config,
          store_in_vault: true 
        });
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save connector');
    } finally {
      setIsSaving(false);
    }
  };

  const handleValidate = async () => {
    setIsValidating(true);
    setValidationResult(null);
    try {
      const res = await validateInstance();
      setValidationResult(res || { status: 'error', message: 'Unknown error' });
    } catch (err) {
      setValidationResult({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' });
    } finally {
      setIsValidating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this connector?')) return;
    try {
      await deleteInstance();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete connector');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div 
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity" 
        onClick={onClose} 
      />
      
      <div className="absolute right-0 top-0 h-full w-full max-w-2xl bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined font-bold text-xl">{connector?.icon || 'hub'}</span>
            </div>
            <div>
              <h2 className="text-xl font-black text-slate-900 leading-tight">
                {instance ? `Manage ${instance.name}` : `Setup ${connector?.name}`}
              </h2>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                {connector?.name} Integration
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-900 transition-colors">
            <span className="material-symbols-outlined font-bold">close</span>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-8">
          <AnimatePresence mode="wait">
            {step === SetupStep.Authenticate && !isAuthed ? (
              <motion.div 
                key="auth"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="flex flex-col items-center justify-center h-full text-center space-y-8"
              >
                <div className="w-20 h-20 rounded-3xl bg-slate-50 flex items-center justify-center text-slate-300">
                  <span className="material-symbols-outlined text-5xl">lock_open</span>
                </div>
                <div className="max-w-xs">
                  <h3 className="text-lg font-black text-slate-900 mb-2">Authentication Required</h3>
                  <p className="text-sm text-slate-500">
                    To connect {connector?.name}, you need to authorize our application to access your data.
                  </p>
                </div>
                <button
                  onClick={handleStartOAuth}
                  className="px-8 py-4 bg-primary text-white font-black rounded-2xl shadow-xl shadow-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center gap-3"
                >
                  <span className="material-symbols-outlined">login</span>
                  Connect {connector?.name}
                </button>
              </motion.div>
            ) : (
              <motion.div 
                key="config"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-8"
              >
                {/* Basic Info */}
                <section className="space-y-4">
                  <h3 className="text-xs font-black uppercase tracking-widest text-primary flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                    General Settings
                  </h3>
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700">Display Name</label>
                    <input 
                      className="w-full p-4 rounded-2xl bg-slate-50 border border-slate-100 focus:bg-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all font-bold text-slate-900"
                      placeholder="e.g. Work Notion"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  {instance && (
                    <div className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-100">
                      <div>
                        <p className="text-sm font-bold text-slate-900">Active Status</p>
                        <p className="text-xs text-slate-500">Enable or disable this connector instance</p>
                      </div>
                      <button 
                        onClick={() => updateInstance({ enabled: !instance.enabled })}
                        className={`w-12 h-6 rounded-full transition-all relative ${instance.enabled ? 'bg-primary' : 'bg-slate-300'}`}
                      >
                        <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-all ${instance.enabled ? 'left-7' : 'left-1'}`} />
                      </button>
                    </div>
                  )}
                </section>

                {/* Document Browser Link */}
                {instance && (
                  <section className="space-y-4 pt-6 border-t border-slate-50">
                    <h3 className="text-xs font-black uppercase tracking-widest text-primary flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                      Data Exploration
                    </h3>
                    <button 
                      onClick={() => setShowDocBrowser(true)}
                      className="w-full p-4 rounded-2xl bg-slate-900 text-white flex items-center justify-between group hover:scale-[1.01] transition-all"
                    >
                      <div className="flex items-center gap-3">
                        <span className="material-symbols-outlined text-primary-light">folder_open</span>
                        <div className="text-left">
                          <p className="text-sm font-bold">Browse Fetched Documents</p>
                          <p className="text-[10px] text-slate-400 uppercase tracking-widest font-black">View {connector?.name} content</p>
                        </div>
                      </div>
                      <span className="material-symbols-outlined text-slate-500 group-hover:translate-x-1 transition-all font-bold">chevron_right</span>
                    </button>
                  </section>
                )}

                {/* Dynamic Config Fields */}
                {connector?.configFields && connector.configFields.length > 0 && (
                  <section className="space-y-6 pt-6 border-t border-slate-50">
                    <h3 className="text-xs font-black uppercase tracking-widest text-primary flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                      Configuration
                    </h3>
                    <div className="grid grid-cols-1 gap-6">
                      {connector.configFields.map(field => (
                        <div key={field.id} className="space-y-2">
                          <label className="text-sm font-bold text-slate-700 flex items-center justify-between">
                            {field.title}
                            {field.required && <span className="text-[10px] text-primary/50 font-black uppercase tracking-tighter bg-primary/5 px-1.5 py-0.5 rounded">Required</span>}
                          </label>
                          {field.type === 'short-input' && (
                            <input 
                              className="w-full p-4 rounded-2xl bg-slate-50 border border-slate-100 focus:bg-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-slate-600"
                              placeholder={field.placeholder}
                              value={config[field.id] || ''}
                              onChange={(e) => setConfig({...config, [field.id]: e.target.value})}
                            />
                          )}
                          {field.type === 'dropdown' && (
                            <select 
                              className="w-full p-4 rounded-2xl bg-slate-50 border border-slate-100 focus:bg-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-slate-600 appearance-none"
                              value={config[field.id] || ''}
                              onChange={(e) => setConfig({...config, [field.id]: e.target.value})}
                            >
                              <option value="">Select an option...</option>
                              {field.options?.map(opt => (
                                <option key={opt.id} value={opt.id}>{opt.label}</option>
                              ))}
                            </select>
                          )}
                          {field.description && <p className="text-xs text-slate-400 italic px-1">{field.description}</p>}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* API Key fallback if mode is apiKey */}
                {connector?.authConfig.mode === 'apiKey' && (
                   <section className="space-y-4 pt-6 border-t border-slate-50">
                    <h3 className="text-xs font-black uppercase tracking-widest text-primary flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                      Authentication
                    </h3>
                    <div className="space-y-2">
                      <label className="text-sm font-bold text-slate-700">
                        {'label' in connector.authConfig ? connector.authConfig.label : 'API Key'}
                      </label>
                      <input 
                        type="password"
                        className="w-full p-4 rounded-2xl bg-slate-50 border border-slate-100 focus:bg-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-slate-600"
                        placeholder={'placeholder' in connector.authConfig ? connector.authConfig.placeholder : 'Enter key...'}
                        value={String(config['api_key'] || config['token'] || config['password'] || '')}
                        onChange={(e) => {
                           // Use whatever key was already there or default to api_key
                           const currentKey = config['api_key'] !== undefined ? 'api_key' : (config['token'] !== undefined ? 'token' : (config['password'] !== undefined ? 'password' : 'api_key'));
                           setConfig({...config, [currentKey]: e.target.value});
                        }}
                      />
                    </div>
                  </section>
                )}

                {/* Validation & Testing */}
                {instance && (
                  <section className="space-y-4 pt-6 border-t border-slate-50">
                    <div className="flex items-center justify-between">
                       <h3 className="text-xs font-black uppercase tracking-widest text-primary flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                        Connection Status
                      </h3>
                      <button 
                        onClick={handleValidate}
                        disabled={isValidating}
                        className="flex items-center gap-2 text-xs font-bold text-primary hover:underline disabled:opacity-50"
                      >
                        <span className={`material-symbols-outlined text-sm ${isValidating ? 'animate-spin' : ''}`}>sync</span>
                        {isValidating ? 'Testing...' : 'Test Connection'}
                      </button>
                    </div>
                    
                    {validationResult && (
                      <div className={`p-4 rounded-2xl flex items-start gap-3 ${validationResult.status === 'ok' ? 'bg-green-50 text-green-700 border border-green-100' : 'bg-red-50 text-red-700 border border-red-100'}`}>
                        <span className="material-symbols-outlined">
                          {validationResult.status === 'ok' ? 'check_circle' : 'error'}
                        </span>
                        <div>
                          <p className="text-sm font-bold">{validationResult.status === 'ok' ? 'Connection Successful' : 'Connection Failed'}</p>
                          {validationResult.message && <p className="text-xs mt-1 opacity-80">{validationResult.message}</p>}
                        </div>
                      </div>
                    )}
                  </section>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div>
            {instance && (
              <button 
                onClick={handleDelete}
                className="px-4 py-2 text-xs font-bold text-red-500 hover:bg-red-50 rounded-xl transition-all"
              >
                Remove Connector
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button 
              onClick={onClose}
              className="px-6 py-3 text-sm font-bold text-slate-500 hover:text-slate-900 transition-all"
            >
              Cancel
            </button>
            {isAuthed && (
              <button 
                onClick={handleSave}
                disabled={isSaving || !name}
                className="px-8 py-3 bg-primary text-white text-sm font-black rounded-2xl shadow-lg shadow-primary/25 hover:brightness-105 active:scale-[0.98] transition-all disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : (instance ? 'Update Changes' : 'Complete Setup')}
              </button>
            )}
          </div>
        </div>
        
        {error && (
          <div className="absolute bottom-24 left-8 right-8 p-4 bg-red-600 text-white rounded-2xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-bottom-2">
            <span className="material-symbols-outlined">warning</span>
            <p className="text-sm font-bold">{error}</p>
            <button onClick={() => setError(null)} className="ml-auto text-white/50 hover:text-white">
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        )}

        <DocumentBrowser 
          isOpen={showDocBrowser}
          onClose={() => setShowDocBrowser(false)}
          instanceId={instance?.id || ''}
          connectorName={connector?.name || ''}
        />
      </div>
    </div>
  );
}

