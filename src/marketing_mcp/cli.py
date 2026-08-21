from __future__ import annotations
import argparse
from marketing_mcp.mcp.server import create_server

def main():
    p=argparse.ArgumentParser(prog="marketing-mcp"); p.add_argument("--transport",choices=["stdio","streamable-http"],default="stdio"); p.add_argument("--host",default=None); p.add_argument("--port",type=int,default=None); args=p.parse_args(); mcp=create_server()
    if args.transport=="stdio": mcp.run("stdio")
    else:
        import uvicorn
        app=mcp.streamable_http_app(host=args.host or "127.0.0.1")
        uvicorn.run(app,host=args.host or "127.0.0.1",port=args.port or 8000)
if __name__=="__main__": main()
