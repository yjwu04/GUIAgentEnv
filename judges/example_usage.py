#!/usr/bin/env python3
"""
Simple example demonstrating the refactored evaluation pipeline.

This script shows how to:
1. Initialize the evaluation pipeline
2. Create a sample agent trajectory
3. Evaluate with all judges
4. Evaluate with specific judges disabled
5. Handle and display results
"""

from evaluation_pipeline import EvaluationPipeline
from agents.agent_base import AgentStepResult
import json


def create_sample_trajectory():
    """Create a sample agent trajectory for demonstration"""
    return [
        AgentStepResult(
            input="Navigate to YouTube homepage",
            action="navigate",
            observation_before={"url": "about:blank"},
            observation_after={"url": "https://youtube.com", "title": "YouTube"},
            output="Successfully navigated to YouTube",
            status="success",
            unsafe_flags=[],
            tool_name="browser",
            action_result={"success": True},
            t_start=0.0,
            t_end=1.2
        ),
        AgentStepResult(
            input="Click on the second video in the first row",
            action="click",
            observation_before={"screenshot": "youtube_before.png"},
            observation_after={"screenshot": "youtube_after.png"},
            output="Clicked on video successfully",
            status="success",
            unsafe_flags=[],
            tool_name="computer",
            action_result={"success": True, "element": "video_2"},
            t_start=1.2,
            t_end=2.5
        ),
        AgentStepResult(
            input="Verify video is playing",
            action="verify",
            observation_before={"video_state": "loading"},
            observation_after={"video_state": "playing"},
            output="Video is playing",
            status="success",
            unsafe_flags=[],
            tool_name="browser",
            action_result={"success": True, "playing": True},
            t_start=2.5,
            t_end=3.0
        )
    ]


def example_basic_evaluation():
    """Example 1: Basic evaluation with all judges"""
    print("=" * 70)
    print("Example 1: Basic Evaluation")
    print("=" * 70)
    
    # Initialize pipeline
    pipeline = EvaluationPipeline()
    
    # Create sample trajectory
    trajectory = create_sample_trajectory()
    
    # Minimal metric configuration
    metric = {
        "task_id": "youtube_video_click",
        "task_description": "Click on the second video in the first row",
        "task_goal": "Navigate to video page and start playback"
    }
    
    # Evaluate
    print("\nEvaluating with all judges...")
    results = pipeline.evaluate(
        result=trajectory,
        metric=metric,
        model_name="claude-3-7-sonnet"
    )
    
    # Display results
    print(f"\nEvaluation completed! {len(results)} judges ran.\n")
    for judge_name, judge_result in results.items():
        print(f"📊 {judge_name.upper()}")
        print(f"   Score: {judge_result.score:.2f}")
        print(f"   Confidence: {judge_result.confidence:.2f}")
        print(f"   Reason: {judge_result.reason[:100]}...")
        print()


def example_disabled_judges():
    """Example 2: Evaluation with specific judges disabled"""
    print("=" * 70)
    print("Example 2: Evaluation with Disabled Judges")
    print("=" * 70)
    
    # Initialize pipeline
    pipeline = EvaluationPipeline()
    
    # Create sample trajectory
    trajectory = create_sample_trajectory()
    
    # Disable some judges
    metric = {
        "task_id": "youtube_video_click",
        "disabled_judges": ["degradation", "pass@k"],  # Only run safety, trajectory, ADR
        "task_description": "Click on the second video in the first row"
    }
    
    # Evaluate
    print("\nEvaluating with degradation and pass@k judges disabled...")
    results = pipeline.evaluate(
        result=trajectory,
        metric=metric,
        model_name="claude-3-7-sonnet"
    )
    
    # Display results
    print(f"\nEvaluation completed! {len(results)} judges ran.\n")
    for judge_name in results.keys():
        print(f"✅ {judge_name}")
    
    print("\nDisabled judges:")
    for judge_name in metric["disabled_judges"]:
        print(f"❌ {judge_name}")


def example_error_handling():
    """Example 3: Handling judge failures"""
    print("=" * 70)
    print("Example 3: Error Handling")
    print("=" * 70)
    
    # Initialize pipeline
    pipeline = EvaluationPipeline()
    
    # Create sample trajectory
    trajectory = create_sample_trajectory()
    
    # Evaluate
    metric = {"task_id": "test_error_handling"}
    results = pipeline.evaluate(trajectory, metric, "claude-3-7-sonnet")
    
    # Check for failures
    print("\nChecking for judge failures...\n")
    successful = []
    failed = []
    
    for judge_name, judge_result in results.items():
        if judge_result.score == 0.0 and judge_result.confidence == 0.0:
            failed.append(judge_name)
            print(f"❌ {judge_name} FAILED")
            print(f"   Error: {judge_result.reason}")
            if "error_type" in judge_result.additional_info:
                print(f"   Type: {judge_result.additional_info['error_type']}")
        else:
            successful.append(judge_name)
            print(f"✅ {judge_name} succeeded (score: {judge_result.score:.2f})")
    
    print(f"\nSummary: {len(successful)} succeeded, {len(failed)} failed")


def example_save_results():
    """Example 4: Saving results to JSON"""
    print("=" * 70)
    print("Example 4: Saving Results to JSON")
    print("=" * 70)
    
    # Initialize pipeline
    pipeline = EvaluationPipeline()
    
    # Create sample trajectory
    trajectory = create_sample_trajectory()
    
    # Evaluate
    metric = {"task_id": "youtube_video_click"}
    results = pipeline.evaluate(trajectory, metric, "claude-3-7-sonnet")
    
    # Convert to serializable format
    serializable_results = {
        judge_name: {
            "score_name": jr.score_name,
            "score": jr.score,
            "confidence": jr.confidence,
            "reason": jr.reason,
            "additional_info": jr.additional_info
        }
        for judge_name, jr in results.items()
    }
    
    # Save to file
    output_file = "example_evaluation_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ Results saved to {output_file}")
    print(f"   Total judges: {len(results)}")
    print(f"   File size: {len(json.dumps(serializable_results))} bytes")


def example_custom_api_key():
    """Example 5: Using custom API key"""
    print("=" * 70)
    print("Example 5: Custom API Key")
    print("=" * 70)
    
    # Initialize with custom API key
    custom_key = "your-custom-api-key-here"
    pipeline = EvaluationPipeline(qwen_api_key=custom_key)
    
    print(f"\n✅ Pipeline initialized with custom API key")
    print(f"   Key prefix: {custom_key[:10]}...")
    print(f"   Available judges: {', '.join(pipeline.judges.keys())}")


def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("EVALUATION PIPELINE USAGE EXAMPLES")
    print("=" * 70 + "\n")
    
    try:
        # Run examples
        example_basic_evaluation()
        print("\n")
        
        example_disabled_judges()
        print("\n")
        
        example_error_handling()
        print("\n")
        
        example_save_results()
        print("\n")
        
        example_custom_api_key()
        print("\n")
        
        print("=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)
        print("\nFor more examples, see USAGE_EXAMPLES.md")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
