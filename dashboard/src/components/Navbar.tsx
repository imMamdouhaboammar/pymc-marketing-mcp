import React from 'react';
import { useAuth } from '../contexts/useAuth';

import { LogOut, Key, LayoutGrid } from 'lucide-react';

interface NavbarProps {
  activeTab: 'user' | 'admin';
  setActiveTab: (tab: 'user' | 'admin') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const { user, profile, isAdmin, logout } = useAuth();

  return (
    <header className="border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14">
          {/* Brand Mark */}
          <div className="flex items-center space-x-3">
            <div className="w-7 h-7 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-950 font-mono font-bold text-xs shadow-sm">
              PY
            </div>
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-sm text-zinc-100 tracking-tight">PyMC Marketing</span>
              <span className="text-[11px] text-zinc-500 font-mono">mcp/v0.5</span>
            </div>
          </div>

          {/* Center Navigation Segmented Switcher */}
          {user && (
            <div className="flex items-center p-1 bg-zinc-900 border border-zinc-800 rounded-lg">
              <button
                onClick={() => setActiveTab('user')}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                  activeTab === 'user'
                    ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/50'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <Key className="w-3.5 h-3.5" />
                <span>API Keys</span>
              </button>

              {isAdmin && (
                <button
                  onClick={() => setActiveTab('admin')}
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    activeTab === 'admin'
                      ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/50'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>Admin</span>
                </button>
              )}
            </div>
          )}

          {/* Right Status & Profile */}
          <div className="flex items-center space-x-3">
            {user ? (
              <div className="flex items-center space-x-3">
                <div className="hidden sm:flex items-center space-x-2 px-2.5 py-1 bg-zinc-900 border border-zinc-800 rounded-full text-[11px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  <span className="text-zinc-300 font-mono truncate max-w-[160px]">{user.email}</span>
                  {profile?.role === 'admin' && (
                    <span className="text-[9px] uppercase font-mono px-1 py-0.2 bg-zinc-800 text-zinc-400 rounded">
                      Admin
                    </span>
                  )}
                </div>

                <button
                  onClick={logout}
                  title="Sign out"
                  className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 border border-zinc-800 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2 text-xs text-zinc-400 font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>us-central1</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
