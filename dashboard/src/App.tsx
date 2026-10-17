import React, { useState } from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { useAuth } from './contexts/useAuth';

import { Navbar } from './components/Navbar';
import { AuthModal } from './components/AuthModal';
import { TeaserLandingPage } from './components/TeaserLandingPage';
import { ApiKeyManager } from './components/ApiKeyManager';
import { ClientConfigGuide } from './components/ClientConfigGuide';
import { UsageTracker } from './components/UsageTracker';
import { AdminPanel } from './components/AdminPanel';
import { ArrowUpRight, ArrowLeft } from 'lucide-react';

const DashboardContent: React.FC = () => {
  const { user, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<'user' | 'admin'>('user');
  const [selectedKey, setSelectedKey] = useState<string>('');
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);

  if (!user) {
    return (
      <div className="min-h-screen bg-[#FAFAF7] text-[#0A0A0A] flex flex-col justify-between">
        <Navbar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onOpenAuth={() => setShowAuthModal(true)}
        />
        {showAuthModal ? (
          <section aria-label="Authentication" className="flex-1 flex flex-col items-center justify-center py-16 px-4 bg-white">
            <button
              onClick={() => setShowAuthModal(false)}
              className="mb-6 text-xs font-mono text-[#6B6B6B] hover:text-[#FF6A2C] flex items-center space-x-1.5 transition-colors font-medium"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to platform overview</span>
            </button>
            <AuthModal />
          </section>
        ) : (
          <main className="flex-1">
            <TeaserLandingPage onOpenAuth={() => setShowAuthModal(true)} />
          </main>
        )}
        <footer className="border-t border-[#ECECEC] bg-white py-8 text-center text-xs text-[#6B6B6B]">
          <div className="max-w-[1240px] mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4 font-mono">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-[#0A0A0A] font-['Outfit']">PyMC Marketing MCP</span>
              <span>•</span>
              <span>v0.5.0</span>
            </div>
            <div className="flex items-center space-x-4 text-xs">
              <a href="#how" className="hover:text-[#FF6A2C]">
                How it works
              </a>
              <a href="#gate" className="hover:text-[#FF6A2C]">
                Decision Gate
              </a>
              <a href="#simulator" className="hover:text-[#FF6A2C]">
                Simulator
              </a>
              <a href="#capabilities" className="hover:text-[#FF6A2C]">
                Capabilities
              </a>
              <a href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp" target="_blank" rel="noreferrer" className="hover:text-[#FF6A2C]">
                GitHub
              </a>
            </div>
          </div>
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
