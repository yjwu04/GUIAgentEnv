import argparse
from pathlib import Path
import importlib.util
import sys
import inspect
import asyncio
import os
import json
from agent_base import AgentAdapter
from configs import ANTHROPIC_API_KEY
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading
import os


def import_agent_class(agent_dir: Path):
    agent_file = agent_dir / "agent.py"
    spec = importlib.util.spec_from_file_location("agent_module", agent_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_module"] = module
    spec.loader.exec_module(module)

    for name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, AgentAdapter) and obj is not AgentAdapter:
            return obj
    raise RuntimeError(f"No subclass of AgentAdapter found in {agent_file}")


def run(agent, dataset=None, http_server=None, http_server_port=8000):
    agent.init(
        api_key=ANTHROPIC_API_KEY,
        model="claude-3-7-sonnet-20250219",
    )
    if dataset:
        dataset_path = Path(__file__).parent.parent / "dataset/testcases" / f"{dataset}.json"
        if not dataset_path.exists():
            print(f"[ERROR] Dataset file not found: {dataset_path}")
            return
        with open(dataset_path, "r", encoding="utf-8") as f:
            testcases = json.load(f)
        for testcase in testcases:
            prompt = testcase.get("prompt", "")
            website = testcase.get("website", "")
            website_url = None
            
            # If prompt does not contain [website], serve the HTML and construct URL
            if website and http_server:
                # Remove leading slash if present, server root is already set to dataset/
                rel_path = website.lstrip("/")
                # Remove 'dataset/' prefix since server already serves from dataset directory
                if rel_path.startswith("dataset/"):
                    rel_path = rel_path[len("dataset/"):]
                website_url = f"http://localhost:{http_server_port}/{rel_path}"
                
                # Debug: Check if the file actually exists
                file_path = Path(__file__).parent.parent / "dataset" / rel_path
                print(f"[DEBUG] Website field: {website}")
                print(f"[DEBUG] Relative path: {rel_path}")
                print(f"[DEBUG] Full file path: {file_path}")
                print(f"[DEBUG] File exists: {file_path.exists()}")
                print(f"[DEBUG] Constructed URL: {website_url}")
                
                if "[website]" not in prompt:
                    import webbrowser
                    webbrowser.open(website_url)
                if "[website]" in prompt:
                    prompt = prompt.replace("[website]", website_url)
            
            print(f"[INFO] Running agent on dataset {dataset}, testcase: {prompt[:60]}... website: {website_url if website_url else 'N/A'}")
            asyncio.run(agent.run(prompt))
    else:
        asyncio.run(agent.run("Find a picture of cat for me"))


def evaluate(results, metric):
    ...


def main():
    parser = argparse.ArgumentParser(description="Run a single agent")
    parser.add_argument("--agents", required=True, help="One agent")
    parser.add_argument("--datasets", required=False, help="Comma-separated datasets")
    parser.add_argument("--metrics", required=False, help="Comma-separated metrics")
    args = parser.parse_args()

    args.datasets = args.datasets.split(",") if args.datasets else []
    args.metrics = args.metrics.split(",") if args.metrics else []

    agent_dir = Path(__file__).parent / args.agents
    Agent = import_agent_class(agent_dir)
    agent = Agent()

    # HTTP server setup
    http_server = None
    http_server_port = 8000
    http_server_root = Path(__file__).parent.parent / "dataset"
    
    # Check if the server root exists
    if not http_server_root.exists():
        print(f"[ERROR] HTTP server root does not exist: {http_server_root}")
        return
    
    print(f"[INFO] HTTP server root: {http_server_root}")
    print(f"[INFO] Current working directory before chdir: {os.getcwd()}")
    os.chdir(http_server_root)
    print(f"[INFO] Current working directory after chdir: {os.getcwd()}")
    
    handler = SimpleHTTPRequestHandler
    # Bind to 0.0.0.0 to accept connections from outside the container
    try:
        http_server = ThreadingHTTPServer(("0.0.0.0", http_server_port), handler)
        print(f"[INFO] Successfully created HTTP server on 0.0.0.0:{http_server_port}")
        print(f"[INFO] Serving {http_server_root} at http://localhost:{http_server_port}/")
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        print(f"[INFO] HTTP server thread started")
        
        # Give the server a moment to start
        import time
        time.sleep(1)
        print(f"[INFO] HTTP server should be ready")
        
        # Test if server is actually responding
        try:
            import urllib.request
            test_url = f"http://localhost:{http_server_port}/"
            urllib.request.urlopen(test_url, timeout=2)
            print(f"[INFO] HTTP server test successful - server is responding")
        except Exception as e:
            print(f"[WARNING] HTTP server test failed: {e}")
            print(f"[INFO] This might be normal if no index file exists")
    except Exception as e:
        print(f"[ERROR] Failed to start HTTP server: {e}")
        http_server = None

    for dataset in args.datasets:
        run(agent, dataset, http_server=http_server, http_server_port=http_server_port)
    if not args.datasets:
        run(agent)

if __name__ == "__main__":
    main()
