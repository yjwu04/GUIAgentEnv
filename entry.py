import argparse
import subprocess
from pathlib import Path
import os
import sys

python_version = {
    "browser_use_agent": "3.11.13",
    "cog_agent": "3.11.13",
    "default_agent": "3.11.13",
    "open_manus_agent": "3.12.11",
    "self_operating_computer_agent": "3.12.11",
    "ui_tars_agent": "3.10.18",
    "web_voyager_agent": "3.10.18",
    "anthropic_agent": "3.11.13",
}

addtional_cmd = {
    "browser_use_agent": [
        "{venv_path}/bin/pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple playwright",
        "{venv_path}/bin/python -m playwright install --with-deps chromium",
    ]
    ,
    "cog_agent": [
        "{venv_path}/bin/pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pyautogui"
    ],
    "open_manus_agent": [
        "{venv_path}/bin/pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple playwright",
        "{venv_path}/bin/python -m playwright install --with-deps chromium",
        "{venv_path}/bin/pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pyautogui"
    ]
}

PYENV_ROOT = Path.home() / ".pyenv"
ENV_PATH = f"{PYENV_ROOT}/shims:{PYENV_ROOT}/bin:" + os.environ.get("PATH", "")


def run_command(cmd, env=None):
    print(f"[INFO] Running: {cmd}", flush=True)
    result = subprocess.run(cmd, shell=True, env=env)
    if result.returncode != 0:
        print("[ERROR] Command failed", flush=True)
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Run agents on datasets with metrics")
    parser.add_argument("--agents", required=True, help="Comma-separated agent names")
    parser.add_argument("--datasets", required=False, default="", help="Comma-separated datasets")
    parser.add_argument("--metrics", required=False, default="", help="Comma-separated metrics")
    parser.add_argument("--task_limit", required=False, default="", help="Limit tasks per dataset for debugging")
    args = parser.parse_args()

    agent_list = args.agents.split(",") if args.agents else []
    datasets_arg = args.datasets
    metrics_arg = args.metrics
    task_limit_arg = args.task_limit
    print(args)

    env = os.environ.copy()
    env["PYENV_ROOT"] = str(PYENV_ROOT)
    env["PATH"] = ENV_PATH
    env["DISPLAY"] = os.environ.get("DISPLAY", ":99")
    if "DISPLAY_NUM" in os.environ:
        env["DISPLAY_NUM"] = os.environ["DISPLAY_NUM"]

    for agent_name in agent_list:
        py_ver = python_version.get(agent_name)
        if not py_ver:
            print(f"[ERROR] Unknown agent: {agent_name}")
            sys.exit(1)

        agent_dir = Path("agents")
        req_file = agent_dir / agent_name / "requirements.txt"
        venv_root = Path(os.getenv("VENV_DIR", ".venvs"))
        venv_path = venv_root / agent_name

        if not venv_path.exists():
            print(f"[INFO] Creating venv for {agent_name} at {venv_path}")
            run_command(f"python -m venv {venv_path}", env=env)
            run_command(
                f"{venv_path}/bin/pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r {req_file}",
                env=env,
            )
            run_command(
                f"{venv_path}/bin/pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple PyYAML",
                env=env,
            )
            if agent_name in addtional_cmd:
                for cmd in addtional_cmd[agent_name]:
                    run_command(cmd.format(venv_path=venv_path), env=env)

        # Ensure excel deps present even if venv already existed
        run_command(f"{venv_path}/bin/pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pandas openpyxl", env=env)

        print(f"[INFO] Using venv for {agent_name} at {venv_path}")
        cmd = (
            f"{venv_path}/bin/python -u "
            f"{agent_dir}/run.py --agent {agent_name}"
        )
        if datasets_arg:
            cmd += f" --datasets {datasets_arg}"
        if metrics_arg:
            cmd += f" --metrics {metrics_arg}"
        if task_limit_arg:
            cmd += f" --task_limit {task_limit_arg}"
        run_command(cmd, env=env)


if __name__ == "__main__":
    main()
