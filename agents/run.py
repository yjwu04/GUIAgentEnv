import argparse
import os
from pathlib import Path
import importlib.util
import sys
import json
import inspect
import asyncio
import time
import subprocess
from datetime import datetime
from agent_base import AgentAdapter
from configs import ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, OPENAI_API_KEY

REPO_ROOT = Path(__file__).resolve().parent.parent
JUDGES_DIR = REPO_ROOT / "judges"
for p in (str(REPO_ROOT), str(JUDGES_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from judges.multimodal_judge import MultimodalJudge
from judges.evaluation_pipeline import EvaluationPipeline


def start_html_server(html_dir, port = 8000):
    return subprocess.Popen(
        ["python", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=html_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


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


def init_agent(agent_name: str, agent: AgentAdapter, screenshot_path) -> bool:
    name = agent_name.lower()
    if name == "browser_use_agent":
        agent.init(
            model_name="deepseek-chat",
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
            max_steps=10,
            img_save_path=screenshot_path,
        )
    elif name == "anthropic_agent":
        agent.init(
            api_key=ANTHROPIC_API_KEY,
            model="claude-3-7-sonnet-20250219",
            img_save_path=screenshot_path
        )
    elif name == "default_agent":
        # Prefer Anthropic computer-use tools so the agent can operate the GUI.
        from agents.default_agent.configs import ModelConfig, ToolConfig

        if not os.getenv("ANTHROPIC_API_KEY") and ANTHROPIC_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

        model_cfg = ModelConfig(
            provider="anthropic",
            name="claude-3-7-sonnet-20250219",
            api_key_env="ANTHROPIC_API_KEY",
        )
        tool_cfg = ToolConfig(group="anthropic_tools")
        agent.init(model_config=model_cfg, tool_config=tool_cfg, max_steps=8,img_save_path=screenshot_path)
    elif name == "cog_agent":
        model_dir = os.getenv("COG_MODEL_DIR", "").strip()
        if not model_dir or model_dir.startswith("/path/to"):
            print("[WARN] Skipping cog_agent: set COG_MODEL_DIR to a valid local model path or HF repo id.")
            return False
        agent.init(model_dir=model_dir, max_steps=5, img_save_path="screenshots")
    elif name == "open_manus_agent":
        agent.init(img_save_path=screenshot_path, max_steps=10)
    elif name == "ui_tars_agent":
        agent.init(base_url="", api_key="", max_steps=3, img_save_path=screenshot_path)
    elif name == "self_operating_computer_agent":
        agent.init(model="qwen-vl", max_steps=10, img_save_path=screenshot_path)
    elif name == "web_voyager_agent":
        openai_key = OPENAI_API_KEY
        if not openai_key:
            print("[WARN] Skipping web_voyager_agent: set OPENAI_API_KEY to enable it.")
            return False
        try:
            agent.init(
                model="gpt-4o",
                key=openai_key,
                headless=False,  # show UI in VNC
                task_dir=screenshot_path,
                downloads_dir=f"{screenshot_path}/downloads",
            )
        except Exception as e:
            print(
                "[WARN] Skipping web_voyager_agent: failed to start Chrome/driver. "
                "Set CHROME_BIN/CHROMEDRIVER to a matching pair and rebuild. "
                f"Error: {e}"
            )
            return False
    else:
        raise RuntimeError(f"Unknown agent: {agent_name}")
    return True


def run(agent_type: str, agent_name: str, agent, dataset, timestamp, project_root, task_limit: int | None = None):
    results = []
    dataset_path = Path(__file__).parent.parent / "dataset" / dataset
    task_jsons = list(dataset_path.rglob("*.json"))
    # task_jsons = ["/Users/ada/Desktop/GeneralAgentFramework/dataset/testcases/Dialect.json"]

    for task_json in task_jsons:
        with open(task_json, "r", encoding="utf-8") as f:
            task_list = json.load(f)
        if task_limit is not None:
            task_list = task_list[:task_limit]
        
        for index, task_params in enumerate(task_list):

            base_screens_dir = Path(os.getenv("SCREENSHOT_DIR", "/home/computeruse/screenshots"))
            output_dir = base_screens_dir / agent_name / dataset / task_params["id"]
            output_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = output_dir / f"{timestamp}"
            init_agent(agent_name, agent, screenshot_path)

            task = task_params["prompt"]

            if agent_type == "PC":
                website_field = task_params.get("website", "")
                server = None

                if website_field.startswith("http"):
                    # External URL, no local server needed
                    task = task.replace("[website]", website_field)
                else:
                    website_path = Path(website_field.lstrip(r"\/"))
                    container_root = Path("/home/computeruse") / website_path.parent
                    entry_html = website_path.name
                    task = task.replace("[website]", f"http://localhost:8000/{entry_html}")
                    server = start_html_server(container_root)
                    time.sleep(1)

                try:
                    print(f"[RUN] starting task {index} in {task_json}", flush=True)
                    start_ts = time.time()
                    result = agent.run(task)
                    if inspect.iscoroutine(result):
                        result = asyncio.run(result)
                    print(f"[RUN] finished task {index} in {task_json}, elapsed={time.time()-start_ts:.1f}s", flush=True)

                    results.append(result)
                finally:
                    if server:
                        server.terminate()
            else:
                package_name = task_params["package_name"]
                apk_path = Path(task_params["apk_path"])

                subprocess.run(["adb", "install", "-r", str(apk_path)], check = True)

                permissions = [
                    "android.permission.CAMERA",
                    "android.permission.ACCESS_FINE_LOCATION",
                    "android.permission.READ_EXTERNAL_STORAGE",
                    "android.permission.WRITE_EXTERNAL_STORAGE"
                ]

                for perm in permissions:
                    subprocess.run(["adb", "shell", "pm", "grant", package_name, perm])

                try:
                    result = agent.run(task)
                    if inspect.iscoroutine(result):
                        result = asyncio.run(result)
                    results.append(result)
                finally:
                    subprocess.run(["adb", "shell", "am", "force-stop", package_name])

    return results, task_jsons
    

def evaluate(result, metric, model_name):
    """
    Evaluate agent trajectory using configured judges
    
    Args:
        result: List[AgentStepResult] from agent execution
        metric: Task-specific configuration including disabled_judges
        model_name: Model name for evaluation
        
    Returns:
        Dict[str, JudgeResult]: Judge results
    """
    pipeline = EvaluationPipeline()
    judge_results = pipeline.evaluate(result, metric, model_name)
    return judge_results

def main():
    parser = argparse.ArgumentParser(description="Run a single agent")
    parser.add_argument("--agent", required=True, help="One agent")
    parser.add_argument("--datasets", required=True, help="Comma-separated datasets")
    parser.add_argument("--task_limit", type=int, default=None, help="Limit number of tasks per dataset for debugging")
    #parser.add_argument("--metrics", required=True, help="Comma-separated metrics")
    args = parser.parse_args()
    print(args)

    args.datasets = args.datasets.split(",") if args.datasets else []
    #args.metrics = args.metrics.split(",") if args.metrics else []

    agent_dir = Path(__file__).parent / args.agent
    Agent = import_agent_class(agent_dir)
    agent = Agent()   

    project_root = Path(__file__).resolve().parent.parent
    results_root = Path(os.getenv("RESULTS_DIR", project_root / "results"))
    config_path = project_root / "config.py"
    print(config_path)

    if config_path.exists():
        spec = importlib.util.spec_from_file_location("config", config_path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        judge_model_name = getattr(config, "JUDGE_MODEL_NAME", "gpt-4o")
    else:
        print(f"[WARN] config.py not found at {config_path}, using default judge model gpt-4o")
        judge_model_name = "gpt-4o"

    if args.agent not in ["app_agent", "mobile_agent_e", "default_agent_mobile"]:
        agent_type = "PC"
    else:
        agent_type = "MOBILE"

    for dataset in args.datasets:
        print(f"[INFO] Running {Agent.__name__} on dataset {dataset}", flush=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        results, task_jsons = run(agent_type, args.agent, agent, dataset, timestamp, project_root, task_limit=args.task_limit)
        all_results = {}

        for task_json in task_jsons:
            with open(task_json, "r", encoding="utf-8") as f:
                task_list = json.load(f)
            
            for index, task_params in enumerate(task_list):
                # Results are in the same order as tasks, so use index to match
                if index >= len(results):
                    print(f"[WARN] No result found for task index {index}, task_id {task_params.get('id', 'unknown')}")
                    continue
                
                result = results[index]
                
                metric = {
                    "task_id": task_params.get("id"),
                    "pass@k_case": task_params.get("pass@k_case", []),
                    "pass@k": task_params.get("pass@k", []),
                }
                # Add all other task_params fields (original_website, noise_type, etc.)
                for key, value in task_params.items():
                    if key not in metric:
                        metric[key] = value
                
                # Merge unsafe_actions and unsafe_consequences if present
                if task_params.get("unsafe_actions") is not None:
                    if isinstance(task_params["unsafe_actions"], dict):
                        metric.update(task_params["unsafe_actions"])
                    else:
                        metric["unsafe_actions"] = task_params["unsafe_actions"]
                    print("unsafe_actions_included")
                        
                if task_params.get("unsafe_consequences") is not None:
                    if isinstance(task_params["unsafe_consequences"], dict):
                        metric.update(task_params["unsafe_consequences"])
                    else:
                        metric["unsafe_consequences"] = task_params["unsafe_consequences"]
                    print("unsafe_consequences_included")

                # Call evaluate() with result, metric, model_name
                print(f"[EVAL] entering judges with metric: {metric} and judge: {judge_model_name}...", flush=True)

                #print("metric:\n\n", metric, "\n\n")
                judge_result = evaluate(result, metric, judge_model_name)
                # Store results
                if dataset not in all_results:
                    all_results[dataset] = {}
                task_id = task_params["id"]
                # Convert JudgeResult objects to dicts for JSON serialization
                serializable_results = {
                    judge_name: {
                        "score_name": jr.score_name,
                        "score": jr.score,
                        "confidence": jr.confidence,
                        "reason": jr.reason,
                        "additional_info": jr.additional_info
                    }
                    for judge_name, jr in judge_result.items()
                }
                all_results[dataset][task_id] = serializable_results
                # Write to JSON file with proper formatting
                output_dir = results_root / args.agent / dataset / task_id
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / f"evaluation_results_{args.agent}_{dataset}_{task_id}_{timestamp}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(all_results[dataset][task_id], f, ensure_ascii=False, indent=4)       
         
                print(f"Evaluation results ({args.agent}, {dataset}, {task_id}, {timestamp}) saved to {output_file}")

        import pandas as pd
        excel_dir = results_root / args.agent / dataset
        excel_dir.mkdir(parents=True, exist_ok=True)
        excel_file = excel_dir / f"evaluation_results_{args.agent}_{dataset}_{timestamp}.xlsx"
        rows = []
        for task_id, jr_dict in all_results[dataset].items():
            for judge_name, jr in jr_dict.items():
                rows.append({
                    "task_id": task_id,
                    "judge_name": judge_name,
                    "score": jr["score"],
                    "confidence": jr["confidence"],
                    "reason": jr["reason"],
                    "additional_info": jr["additional_info"]
                })
        df = pd.DataFrame(rows)
        df.to_excel(excel_file, index=False)
        print(f"All evaluation results also saved to {excel_file}")

if __name__ == "__main__":
    main()
