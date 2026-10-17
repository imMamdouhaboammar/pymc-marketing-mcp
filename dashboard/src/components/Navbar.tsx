import React, { useState } from 'react';
import { useAuth } from '../contexts/useAuth';
import { LogOut, Key, LayoutGrid, Menu, ArrowRight } from 'lucide-react';

interface NavbarProps {
  activeTab: 'user' | 'admin';
  setActiveTab: (tab: 'user' | 'admin') => void;
  onOpenAuth?: () => void;
}

function PublicNavbar({ onOpenAuth }: { onOpenAuth?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="teaser-header">
      <a className="teaser-skip" href="#main-content">
        Skip to content
      </a>
      <div className="teaser-container teaser-nav-row">
        <a
          className="teaser-wordmark"
          href="#hero-title"
          aria-label="PyMC Marketing MCP home"
        >
          PyMC Marketing <span>MCP</span>
        </a>
        <nav
          id="public-navigation"
          className="teaser-public-nav"
          aria-label="Public navigation"
          data-open={open}
        >
          <a href="#how-it-works" onClick={() => setOpen(false)}>
            How it works
          </a>
          <a href="#your-work" onClick={() => setOpen(false)}>
            Your work
          </a>
          <a href="#quickstart" onClick={() => setOpen(false)}>
            Get started
          </a>
          <a
            href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub repository (opens in a new tab)"
          >
            GitHub
          </a>
        </nav>
        <div className="teaser-header-actions">
          <button type="button" className="teaser-signin" onClick={onOpenAuth}>
            Sign in
          </button>
          <a className="teaser-primary nav-sample" href="#quickstart">
            Try the sample <ArrowRight size={15} aria-hidden="true" />
          </a>
          <button
            type="button"
            className="teaser-menu-button"
            aria-expanded={open}
            aria-controls="public-navigation"
            onClick={() => setOpen(!open)}
          >
            Menu <Menu size={17} aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  );
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, onOpenAuth }) => {
  const { user, profile, isAdmin, logout } = useAuth();

  if (!user) return <PublicNavbar onOpenAuth={onOpenAuth} />;

  return (
    <header className="border-b border-[#ECECEC] bg-[#FFFFFF]/90 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          {/* Brand Mark: PrePilot Wave Icon */}
          <div className="flex items-center space-x-3">
            <a href="/" className="flex items-center space-x-2.5 group">
              <div className="w-8 h-8 rounded-xl bg-[#FFF4ED] border border-[#FFE8D6] flex items-center justify-center shadow-sm group-hover:scale-105 transition-transform">
                <svg className="w-5 h-5" viewBox="0 0 32 32" fill="none" aria-hidden="true">
                  <path d="M2 16 Q5 6 9 13 T16 13 T23 13 T30 13" stroke="#FF6A2C" strokeWidth="3.5" strokeLinecap="round" fill="none" />
                  <path d="M2 22 Q5 12 9 19 T16 19 T23 19 T30 19" stroke="#FF6A2C" strokeWidth="3.5" strokeLinecap="round" fill="none" opacity="0.45" />
                </svg>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="font-bold text-base text-[#0A0A0A] tracking-tight font-['Outfit']">PyMC Marketing</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#FFF4ED] text-[#FF6A2C] border border-[#FFE8D6] font-mono">
                  MCP
                </span>
              </div>
            </a>
          </div>

          {/* Center Navigation Switcher for Logged-In Users */}
          {user && (
            <div className="flex items-center p-1 bg-[#FAFAF7] border border-[#ECECEC] rounded-xl">
              <button
                onClick={() => setActiveTab('user')}
                className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'user'
                    ? 'bg-white text-[#0A0A0A] shadow-sm border border-[#ECECEC]'
                    : 'text-[#6B6B6B] hover:text-[#0A0A0A]'
                }`}
              >
                <Key className="w-3.5 h-3.5" />
                <span>API Keys</span>
              </button>

              {isAdmin && (
                <button
                  onClick={() => setActiveTab('admin')}
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                    activeTab === 'admin'
                      ? 'bg-white text-[#0A0A0A] shadow-sm border border-[#ECECEC]'
                      : 'text-[#6B6B6B] hover:text-[#0A0A0A]'
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>Admin</span>
                </button>
              )}
            </div>
          )}

          {/* Right Status & Profile / Action */}
          <div className="flex items-center space-x-3">
            <a
              href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp"
              target="_blank"
              rel="noreferrer"
              aria-label="GitHub repository (opens in a new tab)"
              className="p-2 rounded-xl text-[#6B6B6B] hover:text-[#0A0A0A] hover:bg-[#FAFAF7] border border-[#ECECEC] transition-colors"
            >
              <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
            </a>

            {user ? (
              <div className="flex items-center space-x-3">
                <div className="hidden sm:flex items-center space-x-2 px-3 py-1 bg-[#FAFAF7] border border-[#ECECEC] rounded-full text-[11px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  <span className="text-[#0A0A0A] font-mono truncate max-w-[160px]">{user.email}</span>
                  {profile?.role === 'admin' && (
                    <span className="text-[9px] uppercase font-mono px-1 py-0.2 bg-[#ECECEC] text-[#0A0A0A] rounded">
                      Admin
                    </span>
                  )}
                </div>

                <button
                  onClick={logout}
                  title="Sign out"
                  className="p-2 rounded-xl text-[#6B6B6B] hover:text-[#0A0A0A] hover:bg-[#FAFAF7] border border-[#ECECEC] transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
};
