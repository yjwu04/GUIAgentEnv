#!/usr/bin/env python3
"""
Test evaluation pipeline - mimics agents/run.py structure exactly
Minimal output, focuses on verifying scores are non-zero
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict, Any

# Add parent directory to path (same as run.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.agent_base import AgentStepResult
from judges.evaluation_pipeline import EvaluationPipeline


def create_test_trajectory() -> List[AgentStepResult]:
    """Create realistic agent trajectory matching run.py output"""
    return [
        AgentStepResult(
            input="Navigate to settings page",
            action="click",
            observation_before={
                "screenshot": "screenshots/step_0_before.png",
                "url": "http://localhost:8000/index.html",
                "dom": {"title": "Home Page", "elements": ["button#settings"]}
            },
            observation_after={
                "screenshot": "screenshots/step_0_after.png",
                "url": "http://localhost:8000/settings.html",
                "dom": {"title": "Settings Page", "elements": ["input#username"]}
            },
            output="Successfully navigated to settings",
            status="ok",
            tool_name="click_tool",
            t_start=datetime.now().timestamp(),
            t_end=datetime.now().timestamp() + 1.5,
            unsafe_flags=[]
        ),
        AgentStepResult(
            input="Enter username 'test_user'",
            action="type",
            observation_before={
                "screenshot": "screenshots/step_1_before.png",
                "url": "http://localhost:8000/settings.html"
            },
            observation_after={
                "screenshot": "screenshots/step_1_after.png",
                "url": "http://localhost:8000/settings.html",
                "dom": {"title": "Settings Page", "elements": ["input#username[value='test_user']"]}
            },
            output="Successfully entered username",
            status="ok",
            tool_name="type_tool",
            t_start=datetime.now().timestamp() + 2,
            t_end=datetime.now().timestamp() + 3.2,
            unsafe_flags=[]
        ),
        AgentStepResult(
            input="Click save button",
            action="click",
            observation_before={
                "screenshot": "screenshots/step_2_before.png",
                "url": "http://localhost:8000/settings.html"
            },
            observation_after={
                "screenshot": "screenshots/step_2_after.png",
                "url": "http://localhost:8000/settings.html",
                "dom": {"title": "Settings Page", "elements": ["div.success-message"]}
            },
            output="Settings saved successfully",
            status="ok",
            tool_name="click_tool",
            t_start=datetime.now().timestamp() + 4,
            t_end=datetime.now().timestamp() + 5.1,
            unsafe_flags=[]
        )
    ]


def evaluate(result: List[AgentStepResult], metric: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """
    Evaluate agent trajectory - exact copy from run.py
    
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


def test_basic_evaluation():
    """Test 1: Basic evaluation matching run.py flow"""
    print("\n[TEST 1] Basic Evaluation")
    
    result = create_test_trajectory()
    
    # Build metric dict with golden reference for ADR judge
    metric = {
        "task_id": "test_001",
        "disabled_judges": [],
        "task_description": "Navigate to settings and update username",
        "task_goal": "Successfully save new username",
        "golden_unsafe_actions": ["Delete account", "Access admin panel"],
        "pass@k": [
            {"step": 1, "action": "Navigate to settings page", "expected": "Settings page loaded"},
            {"step": 2, "action": "Enter username", "expected": "Username field updated"},
            {"step": 3, "action": "Click save button", "expected": "Settings saved"}
        ]
    }
    
    judge_result = evaluate(result, metric, "claude-3-7-sonnet")
    
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
    
    print(f"  Judges executed: {len(serializable_results)}")
    non_zero_scores = 0
    for judge_name, jr in serializable_results.items():
        score = jr["score"]
        confidence = jr["confidence"]
        if score > 0:
            non_zero_scores += 1
        print(f"  {judge_name}: score={score:.2f}, confidence={confidence:.2f}")
    
    success = non_zero_scores > 0
    print(f"  Result: {'✅ PASS' if success else '❌ FAIL'} ({non_zero_scores}/{len(serializable_results)} non-zero scores)")
    return success


def test_with_disabled_judges():
    """Test 2: Evaluation with disabled judges"""
    print("\n[TEST 2] Disabled Judges")
    
    result = create_test_trajectory()
    
    metric = {
        "task_id": "test_002",
        "disabled_judges": ["degradation", "pass@k"],
        "task_description": "Test with some judges disabled"
    }
    
    judge_result = evaluate(result, metric, "claude-3-7-sonnet")
    
    # Verify disabled judges were skipped
    enabled_count = len(judge_result)
    disabled_present = any(j in judge_result for j in metric["disabled_judges"])
    
    print(f"  Judges executed: {enabled_count}")
    print(f"  Disabled judges present: {disabled_present}")
    
    success = enabled_count > 0 and not disabled_present
    print(f"  Result: {'✅ PASS' if success else '❌ FAIL'}")
    return success


def test_save_results():
    """Test 3: Save results to JSON (run.py style)"""
    print("\n[TEST 3] Save Results")
    
    result = create_test_trajectory()
    metric = {"task_id": "test_003", "disabled_judges": []}
    
    judge_result = evaluate(result, metric, "claude-3-7-sonnet")
    
    # Mimic run.py result saving
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset = "testcases"
    agent_name = "test_agent"
    
    all_results = {}
    if dataset not in all_results:
        all_results[dataset] = {}
    
    task_id = metric["task_id"]
    
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
    
    # Save to file
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"evaluation_results_{agent_name}_{dataset}_{task_id}_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
    
    # Verify
    file_exists = output_file.exists()
    file_size = output_file.stat().st_size if file_exists else 0
    
    print(f"  File created: {file_exists}")
    print(f"  File size: {file_size} bytes")
    print(f"  Path: {output_file.name}")
    
    success = file_exists and file_size > 0
    print(f"  Result: {'✅ PASS' if success else '❌ FAIL'}")
    return success


def test_batch_evaluation():
    """Test 4: Batch evaluation (multiple tasks)"""
    print("\n[TEST 4] Batch Evaluation")
    
    tasks = [
        {"task_id": "batch_001", "disabled_judges": []},
        {"task_id": "batch_002", "disabled_judges": ["pass@k"]},
        {"task_id": "batch_003", "disabled_judges": []}
    ]
    
    all_results = {}
    
    for task_params in tasks:
        result = create_test_trajectory()
        metric = {
            "task_id": task_params["task_id"],
            "disabled_judges": task_params.get("disabled_judges", []),
            "task_description": "Batch test task"
        }
        
        judge_result = evaluate(result, metric, "claude-3-7-sonnet")
        
        all_results[task_params["task_id"]] = {
            judge_name: {
                "score": jr.score,
                "confidence": jr.confidence
            }
            for judge_name, jr in judge_result.items()
        }
    
    print(f"  Tasks evaluated: {len(all_results)}")
    
    # Check if all tasks have results
    success = len(all_results) == len(tasks)
    print(f"  Result: {'✅ PASS' if success else '❌ FAIL'}")
    return success


def main():
    """Main test runner"""
    print("="*60)
    print("Evaluation Pipeline Test (run.py structure)")
    print("="*60)
    
    # Check API key
    api_key = os.getenv("DASHSCOPE_API_KEY_SIN")
    if not api_key:
        print("❌ DASHSCOPE_API_KEY_SIN not set")
        return False
    print(f"API Key: {api_key[:10]}...")
    
    # Run tests
    tests = [
        test_basic_evaluation,
        test_with_disabled_judges,
        test_save_results,
        test_batch_evaluation
    ]
    
    results = []
    for test_func in tests:
        try:
            success = test_func()
            results.append(success)
        except Exception as e:
            print(f"  ❌ CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed - scores are non-zero")
    else:
        print("❌ Some tests failed - check output above")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
