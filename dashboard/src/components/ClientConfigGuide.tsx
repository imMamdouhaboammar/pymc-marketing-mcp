import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface ClientConfigGuideProps {
  apiKey: string;
}

const SERVER_URL = 'https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp';

export const ClientConfigGuide: React.FC<ClientConfigGuideProps> = ({ apiKey }) => {
  const [activeTab, setActiveTab] = useState<'claude' | 'claudecode' | 'cursor' | 'codex' | 'python'>('claude');
  const [copied, setCopied] = useState(false);

  const displayKey = apiKey || 'YOUR_API_KEY_HERE';

  const configs = {
    claude: {
      title: 'Claude Desktop',
      file: 'claude_desktop_config.json',
      pathText: 'Library/Application Support/Claude/claude_desktop_config.json',
      code: JSON.stringify(
        {
          mcpServers: {
            'pymc-marketing': {
              url: SERVER_URL,
              headers: {
                Authorization: `Bearer ${displayKey}`,
              },
            },
          },
        },
        null,
        2
      ),
    },
    claudecode: {
      title: 'Claude Code CLI',
      file: 'Terminal',
      pathText: 'Run in terminal:',
      code: `claude mcp add pymc-marketing ${SERVER_URL} --header "Authorization: Bearer ${displayKey}"`,
    },
    cursor: {
      title: 'Cursor / Antigravity',
      file: 'Settings > Features > MCP',
      pathText: 'Streamable HTTP Endpoint:',
      code: JSON.stringify(
        {
          name: 'pymc-marketing',
          type: 'sse',
          url: `${SERVER_URL}?token=${displayKey}`,
        },
        null,
        2
      ),
    },
    codex: {
      title: 'OpenAI Codex / Stdio',
      file: 'mcp.json (mcp-remote bridge)',
      pathText: 'Bridge for stdio environments:',
      code: JSON.stringify(
        {
          mcpServers: {
            'pymc-marketing': {
              command: 'npx',
              args: ['-y', 'mcp-remote', `${SERVER_URL}?token=${displayKey}`],
            },
          },
        },
        null,
        2
      ),
    },
    python: {
      title: 'Python SDK / Custom Agent',
      file: 'agent.py',
      pathText: 'Python Async MCP Client:',
      code: `import asyncio
import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    url = "${SERVER_URL}"
    headers = {"Authorization": "Bearer ${displayKey}"}

    async with (
        httpx2.AsyncClient(headers=headers) as http_client,
        streamable_http_client(url, http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        print(f"Connected! Available tools: {len(tools.tools)}")

asyncio.run(main())`,
    },
  };

  const current = configs[activeTab];

  const handleCopy = () => {
    navigator.clipboard.writeText(current.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100 tracking-tight">Client Connection Snippets</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Pre-filled configuration manifests for AI agents and coding tools.
          </p>
        </div>

        {/* Tab switchers */}
        <div className="flex flex-wrap items-center gap-1 bg-zinc-950 p-0.5 rounded-lg border border-zinc-800">
          {(Object.keys(configs) as Array<keyof typeof configs>).map((key) => {
            const tab = configs[key];
            return (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  activeTab === key
                    ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/50'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {tab.title}
              </button>
            );
          })}
        </div>
      </div>

      {/* Code Console */}
      <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950 font-mono text-xs">
        <div className="flex items-center justify-between px-3.5 py-2 bg-zinc-900/80 border-b border-zinc-800/80 text-[11px] text-zinc-400">
          <div className="flex items-center space-x-2 truncate">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400"></span>
            <span className="text-zinc-200">{current.file}</span>
            <span className="text-zinc-600">•</span>
            <span className="text-zinc-500 text-[10px] truncate">{current.pathText}</span>
          </div>

          <button
            onClick={handleCopy}
            className="flex items-center space-x-1 px-2 py-0.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded border border-zinc-700/60 transition-colors text-[11px]"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>

        <pre className="p-3.5 text-zinc-300 overflow-x-auto leading-relaxed selection:bg-zinc-800">
          {current.code}
        </pre>
      </div>
    </div>
  );
};
