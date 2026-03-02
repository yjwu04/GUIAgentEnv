# NoisyBenchmark GUI Agent Environment

This project runs GUI agents inside Dockerized desktop/mobile environments and evaluates them on noisy web/app tasks.

## What this repo provides

- A Linux desktop GUI runtime (Xvfb + XFCE + noVNC) for PC agents.
- An Android emulator GUI runtime (noVNC + AVD) for mobile experiments.
- Unified agent execution and judging pipeline.
- Persisted artifacts: screenshots, logs, JSON results, and Excel summaries.

## Repository layout

- `linux/`: desktop GUI container image and startup script.
- `android/`: Android emulator container image and startup script.
- `agents/`: agent adapters and execution pipeline.
- `dataset/`: benchmark tasks (`testcases`, `runnable`, `mobile_testcases`, etc.).
- `judges/`: multimodal evaluation and scoring pipeline.
- `run_experiment.sh`: host launcher for desktop-agent Docker runs.
- `entry.py`: creates per-agent venvs and dispatches `agents/run.py`.

## Prerequisites

- Docker installed and running.
- Linux/macOS host with port `6080` available.
- Valid model API keys configured in code/config (see below).

## Configure model access

1. Update keys in `agents/configs.py` for the providers you plan to use:
   - `ANTHROPIC_API_KEY`
   - `DEEPSEEK_API_KEY`
   - `OPENAI_API_KEY`
   - `QWEN_API_KEY` (if needed by selected components)
2. Choose judge model in `config.py` via `JUDGE_MODEL_NAME`.

Security note: avoid committing real secrets. Use environment-managed secrets or local-only config handling in your workflow.

## Build the desktop GUI image

```bash
docker build -t desktop-agent -f linux/Dockerfile .
```

## Run a desktop benchmark (recommended path)

```bash
./run_experiment.sh --agents anthropic_agent --datasets testcases --task_limit 1
```

Then open noVNC in your browser:

- [http://localhost:6080](http://localhost:6080)

### Common arguments

- `--agents`: comma-separated agent names (required by this workflow).
- `--datasets`: comma-separated dataset folders under `dataset/` (required in practice).
- `--task_limit`: optional per-task-file cap for quick debugging.

Supported agent names in `entry.py`:

- `anthropic_agent`
- `browser_use_agent`
- `default_agent`
- `open_manus_agent`
- `self_operating_computer_agent`
- `ui_tars_agent`
- `web_voyager_agent`
- `cog_agent`

## Output locations

`run_experiment.sh` persists outputs on host:

- `results/<agent>/`: evaluation JSON/XLSX outputs.
- `results/<agent>/logs/`: container startup/runtime logs.
- `screenshots/<agent>/`: before/after screenshots.
- `.run_cache/venvs/`: reusable Python virtual environments.

## Android GUI environment (optional)

Build:

```bash
docker build -t android-agent -f android/Dockerfile android
```

Run:

```bash
docker run -it --rm -p 6080:6080 android-agent
```

Open:

- [http://localhost:6080](http://localhost:6080)

## Troubleshooting

- noVNC not reachable:
  - Ensure `docker run` mapped `-p 6080:6080`.
  - Check logs in `results/<agent>/logs/start.log`.
- Agent skipped or fails at init:
  - Verify required key/model config in `agents/configs.py`.
  - For `cog_agent`, set a valid `COG_MODEL_DIR`.
- Chrome/driver issues for `web_voyager_agent`:
  - Ensure matching browser/driver in image and rebuild.
- Dataset argument errors:
  - Pass `--datasets` explicitly (for example `testcases`).
- Do not pass `--metrics` via `entry.py` currently:
  - `agents/run.py` does not accept this argument.
