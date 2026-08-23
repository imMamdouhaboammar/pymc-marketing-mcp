import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/useAuth';
import {
  collection,
  query,
  where,
  getDocs,
  addDoc,
  updateDoc,
  doc,
  serverTimestamp
} from 'firebase/firestore';
import { db } from '../firebase';
import type { ApiKeyItem } from '../types';
import { Plus, Copy, Check, Trash2, RefreshCw } from 'lucide-react';

interface ApiKeyManagerProps {
  onSelectKey: (key: string) => void;
  selectedKey: string;
}

export const ApiKeyManager: React.FC<ApiKeyManagerProps> = ({ onSelectKey, selectedKey }) => {
  const { user } = useAuth();
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [keyName, setKeyName] = useState('');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const q = query(collection(db, 'api_keys'), where('ownerUid', '==', user.uid));
      const querySnapshot = await getDocs(q);
      const items: ApiKeyItem[] = [];
      querySnapshot.forEach((docSnap) => {
        const data = docSnap.data();
        items.push({
          id: docSnap.id,
          name: data.name || 'API Key',
          keyPrefix: data.keyPrefix || 'mcp_live_...',
          ownerUid: data.ownerUid,
          ownerEmail: data.ownerEmail,
          status: data.status || 'active',
          createdAt: data.createdAt?.toDate ? data.createdAt.toDate().toISOString() : data.createdAt || new Date().toISOString(),
          requestCount: data.requestCount || 0,
        });
      });
      setKeys(items);
      if (items.length > 0 && !selectedKey) {
        onSelectKey(items[0].keyPrefix);
      }
    } catch (err) {
      console.warn('Could not fetch from Firestore, checking local storage:', err);
      const local = localStorage.getItem(`keys_${user.uid}`);
      if (local) {
        const parsed = JSON.parse(local);
        setKeys(parsed);
        if (parsed.length > 0 && !selectedKey) {
          onSelectKey(parsed[0].keySecret || parsed[0].keyPrefix);
        }
      }
    } finally {
      setLoading(false);
    }
  }, [user, onSelectKey, selectedKey]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);


  const generateRandomKey = (): string => {
    const array = new Uint8Array(24);
    window.crypto.getRandomValues(array);
    const hex = Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join('');
    return `mcp_live_${hex}`;
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;

    const fullSecret = generateRandomKey();
    const prefix = `${fullSecret.substring(0, 14)}...${fullSecret.substring(fullSecret.length - 4)}`;

    const newItem: ApiKeyItem = {
      id: `key_${Date.now()}`,
      name: keyName || 'Developer Key',
      keySecret: fullSecret,
      keyPrefix: prefix,
      ownerUid: user.uid,
      ownerEmail: user.email || '',
      status: 'active',
      createdAt: new Date().toISOString(),
      requestCount: 0,
    };

    try {
      const docRef = await addDoc(collection(db, 'api_keys'), {
        name: newItem.name,
        keyPrefix: prefix,
        keyHash: fullSecret,
        ownerUid: user.uid,
        ownerEmail: user.email || '',
        status: 'active',
        createdAt: serverTimestamp(),
        requestCount: 0,
      });
      newItem.id = docRef.id;
    } catch (err) {
      console.warn('Firestore fallback to local storage:', err);
    }

    const updatedKeys = [newItem, ...keys];
    setKeys(updatedKeys);
    localStorage.setItem(`keys_${user.uid}`, JSON.stringify(updatedKeys));
    setNewlyCreatedKey(fullSecret);
    onSelectKey(fullSecret);
    setKeyName('');
    setIsCreating(false);
  };

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm('Revoke this key? Connected clients will lose access immediately.')) return;
    try {
      await updateDoc(doc(db, 'api_keys', keyId), { status: 'revoked' });
    } catch (err) {
      console.warn(err);
    }
    const updated = keys.map((k) => (k.id === keyId ? { ...k, status: 'revoked' as const } : k));
    setKeys(updated);
    if (user) {
      localStorage.setItem(`keys_${user.uid}`, JSON.stringify(updated));
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100 tracking-tight">API Keys</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Cryptographic tokens for authenticating Claude, Cursor, and custom MCP clients.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={fetchKeys}
            className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-md border border-zinc-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-semibold rounded-md transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create key</span>
          </button>
        </div>
      </div>

      {/* Newly Minted Secret Notice */}
      {newlyCreatedKey && (
        <div className="mb-4 p-3.5 bg-zinc-950 border border-emerald-500/30 rounded-lg">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="font-semibold text-emerald-400 flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span>New Secret Generated</span>
            </span>
            <button
              onClick={() => setNewlyCreatedKey(null)}
              className="text-zinc-500 hover:text-zinc-300 text-[11px]"
            >
              Dismiss
            </button>
          </div>
          <div className="flex items-center space-x-2 bg-zinc-900 border border-zinc-800 rounded-md p-1.5">
            <code className="text-xs text-zinc-200 font-mono select-all flex-1 px-1.5 truncate">
              {newlyCreatedKey}
            </code>
            <button
              onClick={() => copyToClipboard(newlyCreatedKey, 'new-key')}
              className="flex items-center space-x-1 px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-[11px] font-medium rounded transition-colors"
            >
              {copiedId === 'new-key' ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400 font-mono">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Create Key Form */}
      {isCreating && (
        <form onSubmit={handleCreateKey} className="mb-4 p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg">
          <label className="block text-[11px] font-medium text-zinc-400 mb-1.5">Key Description</label>
          <div className="flex flex-col sm:flex-row items-center gap-2">
            <input
              type="text"
              required
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder="e.g. Claude Desktop Production"
              className="w-full bg-zinc-900 border border-zinc-700 focus:border-zinc-500 rounded-md py-1.5 px-2.5 text-xs text-zinc-100 placeholder-zinc-600 outline-none"
            />
            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <button
                type="submit"
                className="w-full sm:w-auto px-3 py-1.5 bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-semibold rounded-md whitespace-nowrap"
              >
                Generate
              </button>
              <button
                type="button"
                onClick={() => setIsCreating(false)}
                className="w-full sm:w-auto px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs rounded-md"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Keys Table */}
      {keys.length === 0 && !loading ? (
        <div className="text-center py-8 border border-dashed border-zinc-800 rounded-lg text-zinc-500 text-xs font-mono">
          No keys active. Click "Create key" to generate one.
        </div>
      ) : (
        <div className="border border-zinc-800/80 rounded-lg overflow-hidden">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="text-[10px] uppercase font-mono tracking-wider text-zinc-500 bg-zinc-950 border-b border-zinc-800">
              <tr>
                <th className="py-2 px-3.5">Name</th>
                <th className="py-2 px-3.5 font-mono">Token</th>
                <th className="py-2 px-3.5">Status</th>
                <th className="py-2 px-3.5">Created</th>
                <th className="py-2 px-3.5">Requests</th>
                <th className="py-2 px-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 bg-zinc-900/20">
              {keys.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => onSelectKey(item.keySecret || item.keyPrefix)}
                  className={`hover:bg-zinc-800/40 cursor-pointer transition-colors ${
                    selectedKey === (item.keySecret || item.keyPrefix) ? 'bg-zinc-800/60' : ''
                  }`}
                >
                  <td className="py-2.5 px-3.5 font-medium text-zinc-200">{item.name}</td>
                  <td className="py-2.5 px-3.5 font-mono text-zinc-400 text-[11px]">
                    <span className="bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800">
                      {item.keyPrefix}
                    </span>
                  </td>
                  <td className="py-2.5 px-3.5">
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono uppercase ${
                        item.status === 'active'
                          ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                          : 'bg-zinc-800 text-zinc-500'
                      }`}
                    >
                      {item.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3.5 text-zinc-400 font-mono text-[11px]">
                    {new Date(item.createdAt).toLocaleDateString()}
                  </td>
                  <td className="py-2.5 px-3.5 font-mono text-zinc-200">
                    {item.requestCount}
                  </td>
                  <td className="py-2.5 px-3.5 text-right">
                    {item.status === 'active' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRevokeKey(item.id);
                        }}
                        title="Revoke Key"
                        className="p-1 text-zinc-500 hover:text-red-400 rounded transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
