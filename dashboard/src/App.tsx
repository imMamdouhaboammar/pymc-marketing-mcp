import React, { useState } from "react";
import "./teaser.css";
import { AuthProvider } from "./contexts/AuthContext";
import { useAuth } from "./contexts/useAuth";

import { Navbar } from "./components/Navbar";
import { AuthModal } from "./components/AuthModal";
import { TeaserLandingPage } from "./components/TeaserLandingPage";
import { ApiKeyManager } from "./components/ApiKeyManager";
import { ClientConfigGuide } from "./components/ClientConfigGuide";
import { UsageTracker } from "./components/UsageTracker";
import { AdminPanel } from "./components/AdminPanel";
import { ArrowUpRight, ArrowLeft } from "lucide-react";

const DashboardContent: React.FC = () => {
  const { user, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<"user" | "admin">("user");
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);

  if (!user) {
    return (
      <div className="teaser-site min-h-screen flex flex-col">
        <Navbar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onOpenAuth={() => setShowAuthModal(true)}
        />
        {showAuthModal ? (
          <main id="main-content" className="teaser-auth" tabIndex={-1}>
            <button
              onClick={() => setShowAuthModal(false)}
              className="teaser-auth-back"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to platform overview</span>
            </button>
            <AuthModal />
          </main>
        ) : (
          <main id="main-content" className="flex-1" tabIndex={-1}>
            <TeaserLandingPage />
          </main>
        )}
        <footer className="teaser-footer">
          <div className="teaser-container teaser-footer-row">
            <p>PyMC Marketing MCP · Open-source marketing science</p>
            <nav aria-label="Footer navigation">
              <a
                href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
              <a
                href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp/blob/main/docs/README.md"
                target="_blank"
                rel="noreferrer"
              >
                Documentation
              </a>
              <a
                href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp/blob/main/LICENSE"
                target="_blank"
                rel="noreferrer"
              >
                Apache 2.0
              </a>
            </nav>
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
