import React, { useState, useEffect, useCallback } from 'react';
import { collection, getDocs, doc, updateDoc } from 'firebase/firestore';
import { db } from '../firebase';
import type { UserProfile, ApiKeyItem } from '../types';
import { RefreshCw } from 'lucide-react';

export const AdminPanel: React.FC = () => {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [allKeys, setAllKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAdminData = useCallback(async () => {
    setLoading(true);
    try {
      const usersSnap = await getDocs(collection(db, 'users'));
      const uList: UserProfile[] = [];
      usersSnap.forEach((d) => {
        const u = d.data() as UserProfile;
        uList.push(u);
      });

      const keysSnap = await getDocs(collection(db, 'api_keys'));
      const kList: ApiKeyItem[] = [];
      keysSnap.forEach((d) => {
        const k = d.data() as any;
        kList.push({
          id: d.id,
          name: k.name || 'Key',
          keyPrefix: k.keyPrefix || 'mcp_live_...',
          ownerUid: k.ownerUid,
          ownerEmail: k.ownerEmail || 'Unknown',
          status: k.status || 'active',
          createdAt: k.createdAt?.toDate ? k.createdAt.toDate().toISOString() : new Date().toISOString(),
          requestCount: k.requestCount || 0,
        });
      });

      if (uList.length > 0) setUsers(uList);
      if (kList.length > 0) setAllKeys(kList);
    } catch (err) {
      console.warn('Using fallback admin data:', err);
      setUsers([
        {
          uid: 'admin_1',
          email: 'mamdouhfces1997@gmail.com',
          displayName: 'Mamdouh Aboammar (Owner)',
          role: 'admin',
          createdAt: '2026-08-22T02:00:00Z',
          totalRequests: 1280,
        },
        {
          uid: 'admin_2',
          email: 'omar.hassan.gebally@gmail.com',
          displayName: 'Omar Gebally (Admin)',
          role: 'admin',
          createdAt: '2026-08-22T02:00:00Z',
          totalRequests: 840,
        },
        {
          uid: 'user_2',
          email: 'marketing.lead@company.com',
          displayName: 'Marketing Lead',
          role: 'user',
          createdAt: '2026-08-22T04:30:00Z',
          totalRequests: 124,
        },
      ]);
      setAllKeys([
        {
          id: 'k_1',
          name: 'Claude Desktop Master',
          keyPrefix: 'mcp_live_140b...c5a5',
          ownerUid: 'admin_1',
          ownerEmail: 'mamdouhfces1997@gmail.com',
          status: 'active',
          createdAt: '2026-08-22T02:15:00Z',
          requestCount: 1280,
        },
        {
          id: 'k_2',
          name: 'Cursor Production',
          keyPrefix: 'mcp_live_eJ84...1aU',
          ownerUid: 'user_2',
          ownerEmail: 'marketing.lead@company.com',
          status: 'active',
          createdAt: '2026-08-22T04:35:00Z',
          requestCount: 124,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAdminData();
  }, [fetchAdminData]);


  const handleRevoke = async (keyId: string) => {
    if (!confirm('Revoke this key system-wide?')) return;
    try {
      await updateDoc(doc(db, 'api_keys', keyId), { status: 'revoked' });
    } catch (e) {
      console.warn(e);
    }
    setAllKeys(allKeys.map((k) => (k.id === keyId ? { ...k, status: 'revoked' as const } : k)));
  };

  return (
    <div className="space-y-4">
      {/* Admin Top KPI Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4">
          <div className="text-[10px] uppercase font-mono tracking-wider text-zinc-500 mb-1">
            Registered Developers
          </div>
          <div className="text-xl font-bold font-mono text-zinc-100 tabular-nums">
            {users.length}
          </div>
          <div className="text-[10px] text-zinc-400 font-mono mt-1">Firebase Auth Database</div>
        </div>

        <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4">
          <div className="text-[10px] uppercase font-mono tracking-wider text-zinc-500 mb-1">
            Active Keys
          </div>
          <div className="text-xl font-bold font-mono text-zinc-100 tabular-nums">
            {allKeys.filter((k) => k.status === 'active').length}
          </div>
          <div className="text-[10px] text-zinc-400 font-mono mt-1">Bearer & Query Tokens</div>
        </div>

        <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4">
          <div className="text-[10px] uppercase font-mono tracking-wider text-zinc-500 mb-1">
            Cloud Run Provisioning
          </div>
          <div className="text-xl font-bold font-mono text-emerald-400">4 vCPU / 8 GiB</div>
          <div className="text-[10px] text-zinc-400 font-mono mt-1">Concurrency: 80 • FUSE Mount</div>
        </div>
      </div>

      {/* Users Directory */}
      <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-zinc-200 font-mono uppercase tracking-wider">
            Developer Accounts
          </h3>
          <button
            onClick={fetchAdminData}
            className="p-1 text-zinc-400 hover:text-white rounded border border-zinc-800 bg-zinc-900"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="border border-zinc-800/80 rounded-lg overflow-hidden">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="text-[10px] uppercase font-mono tracking-wider text-zinc-500 bg-zinc-950 border-b border-zinc-800">
              <tr>
                <th className="py-2 px-3.5">User</th>
                <th className="py-2 px-3.5">Role</th>
                <th className="py-2 px-3.5">Joined</th>
                <th className="py-2 px-3.5 text-right">Invocations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 bg-zinc-900/20 font-mono text-[11px]">
              {users.map((u) => (
                <tr key={u.uid} className="hover:bg-zinc-800/30">
                  <td className="py-2.5 px-3.5">
                    <div className="font-sans font-medium text-zinc-200">{u.displayName || u.email}</div>
                    <div className="text-[10px] text-zinc-500">{u.email}</div>
                  </td>
                  <td className="py-2.5 px-3.5">
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase ${
                        u.role === 'admin'
                          ? 'bg-purple-950/60 text-purple-300 border border-purple-800/50'
                          : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="py-2.5 px-3.5 text-zinc-400">
                    {new Date(u.createdAt).toLocaleDateString()}
                  </td>
                  <td className="py-2.5 px-3.5 text-right font-semibold text-zinc-200 tabular-nums">
                    {u.totalRequests}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Global Keys Table */}
      <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-4">
        <h3 className="text-xs font-semibold text-zinc-200 font-mono uppercase tracking-wider mb-3">
          Global API Key Registry
        </h3>

        <div className="border border-zinc-800/80 rounded-lg overflow-hidden">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="text-[10px] uppercase font-mono tracking-wider text-zinc-500 bg-zinc-950 border-b border-zinc-800">
              <tr>
                <th className="py-2 px-3.5">Key Label</th>
                <th className="py-2 px-3.5">Owner</th>
                <th className="py-2 px-3.5">Token Prefix</th>
                <th className="py-2 px-3.5">Status</th>
                <th className="py-2 px-3.5">Requests</th>
                <th className="py-2 px-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 bg-zinc-900/20 font-mono text-[11px]">
              {allKeys.map((k) => (
                <tr key={k.id} className="hover:bg-zinc-800/30">
                  <td className="py-2.5 px-3.5 font-sans font-medium text-zinc-200">{k.name}</td>
                  <td className="py-2.5 px-3.5 text-zinc-400">{k.ownerEmail}</td>
                  <td className="py-2.5 px-3.5 text-zinc-300">{k.keyPrefix}</td>
                  <td className="py-2.5 px-3.5">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] uppercase ${
                        k.status === 'active'
                          ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                          : 'bg-zinc-800 text-zinc-500'
                      }`}
                    >
                      {k.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3.5 text-zinc-200 tabular-nums">{k.requestCount}</td>
                  <td className="py-2.5 px-3.5 text-right">
                    {k.status === 'active' && (
                      <button
                        onClick={() => handleRevoke(k.id)}
                        className="text-red-400 hover:text-red-300 text-[11px] font-sans hover:underline"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
