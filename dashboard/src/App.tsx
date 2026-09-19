import React, { useState } from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './contexts/useAuth';

import { Navbar } from './components/Navbar';
import { AuthModal } from './components/AuthModal';
import { ApiKeyManager } from './components/ApiKeyManager';
import { ClientConfigGuide } from './components/ClientConfigGuide';
import { UsageTracker } from './components/UsageTracker';
import { AdminPanel } from './components/AdminPanel';
import { ArrowUpRight } from 'lucide-react';

const DashboardContent: React.FC = () => {
  const { user, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<'user' | 'admin'>('user');
  const [selectedKey, setSelectedKey] = useState<string>('');

  if (!user) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col justify-between">
        <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
        <section aria-label="Authentication" className="flex-1 flex items-center justify-center">
          <AuthModal />
        </section>
        <footer className="border-t border-zinc-900 py-4 text-center text-xs text-zinc-600 font-mono">
          PyMC Marketing MCP Server • v0.4.0
        </footer>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6">
        {/* Subtle Breadcrumb & Status Bar */}
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-zinc-800/80">
          <div>
            <div className="flex items-center space-x-2 text-xs text-zinc-400 font-mono mb-1">
              <span>pymc-marketing</span>
              <span>/</span>
              <span className="text-zinc-200">{activeTab === 'admin' ? 'admin-console' : 'portal'}</span>
            </div>
            <h1 className="text-lg font-semibold text-zinc-100 tracking-tight">
              {activeTab === 'admin' ? 'Administration & Key Registry' : 'Developer Portal & Keys'}
            </h1>
          </div>

          <div className="flex items-center space-x-2">
            <a
              href="https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/health"
              target="_blank"
              rel="noreferrer"
              aria-label="/health endpoint (opens in a new tab)"
              className="flex items-center space-x-1.5 px-2.5 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-xs font-mono rounded-md transition-colors"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span>/health</span>
              <ArrowUpRight className="w-3 h-3 text-zinc-500" />
            </a>

            <a
              href="https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp"
              target="_blank"
              rel="noreferrer"
              aria-label="/mcp endpoint (opens in a new tab)"
              className="flex items-center space-x-1.5 px-2.5 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-xs font-mono rounded-md transition-colors"
            >
              <span>/mcp</span>
              <ArrowUpRight className="w-3 h-3 text-zinc-500" />
            </a>
          </div>
        </div>

        {/* Dynamic Views */}
        {activeTab === 'admin' && isAdmin ? (
          <AdminPanel />
        ) : (
          <div className="space-y-6">
            <UsageTracker />
            <ApiKeyManager onSelectKey={setSelectedKey} selectedKey={selectedKey} />
            <ClientConfigGuide apiKey={selectedKey} />
          </div>
        )}
      </main>

      <footer className="border-t border-zinc-900 bg-zinc-950 py-4 mt-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between text-[11px] text-zinc-500 font-mono gap-2">
          <div>PyMC Marketing MCP • Google Cloud Run us-central1</div>
          <div className="flex items-center space-x-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>Auth & Streamable HTTP Active</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export function App() {
  return (
    <AuthProvider>
      <DashboardContent />
    </AuthProvider>
  );
}

export default App;
