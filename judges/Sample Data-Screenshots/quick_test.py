"""
Quick Test Script for Qwen-VL Framework with YouTube Sample
"""

import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to import agents module
sys.path.append(str(Path(__file__).parent.parent))

from agents.agent_base import AgentStepResult
from judges.qwen_vl_caller import QwenVLCaller, call_qwen_vl

def quick_test_setup():
    """Quick setup and test of the Qwen-VL framework"""
    
    print("🚀 Quick Test: Qwen-VL Framework with YouTube Sample")
    print("-" * 50)
    
    # Step 1: Check API key
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ DASHSCOPE_API_KEY not found!")
        print("Please set it: export DASHSCOPE_API_KEY='your_key_here'")
        return False
    else:
        print("✅ API key found")
    
    # Step 2: Check sample images
    image_paths = [
        "Sample Data-Screenshots/youtube_before.png",
        "Sample Data-Screenshots/youtube_after.png"
    ]
    
    for path in image_paths:
        if os.path.exists(path):
            print(f"✅ Found: {path}")
        else:
            print(f"❌ Missing: {path}")
            print(f"   Please ensure this screenshot exists")
    
    return True

def create_simple_youtube_step() -> AgentStepResult:
    """Create a simple YouTube click step for testing"""
    
    return AgentStepResult(
        input="Click on the second video in the first row of YouTube",
        action="click",
        observation_before={
            "screenshot": "Sample Data-Screenshots/youtube_before.png",
            "url": "https://www.youtube.com"
        },
        observation_after={
            "screenshot": "Sample Data-Screenshots/youtube_after.png", 
            "url": "https://www.youtube.com/watch?v=sample_id"
        },
        action_result={
            "success": True,
            "element_clicked": "second_video_thumbnail"
        },
        output="Successfully clicked second video, video page loaded",
        status="ok",
        tool_name="browser",
        t_start=1.0,
        t_end=2.5
    )

def test_qwen_vl_basic():
    """Test basic Qwen-VL functionality"""
    
    print("\n🧪 Testing Basic Qwen-VL Call...")
    
    try:
        caller = QwenVLCaller()
        
        # Simple text-only test first
        messages = [
            {"role": "system", "content": "You are a helpful evaluator."},
            {"role": "user", "content": "Evaluate this task: 'Click second video on YouTube'. Return JSON with score (0-1) and reasoning."}
        ]
        
        response = caller.call_multimodal(messages)
        result = caller.extract_json_from_response(response)
        
        print("✅ Basic call successful!")
        print(f"   Result: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Basic call failed: {e}")
        return False

def test_qwen_vl_multimodal():
    """Test multimodal functionality with images"""
    
    print("\n🖼️  Testing Multimodal Call...")
    
    try:
        caller = QwenVLCaller()
        
        text = """
        Analyze these YouTube screenshots:
        1. Before: Shows YouTube homepage
        2. After: Shows video playing page
        
        Task: Click on second video in first row
        
        Return JSON: {"success": boolean, "score": float, "reasoning": string}
        """
        
        images = [
            "Sample Data-Screenshots/youtube_before.png",
            "Sample Data-Screenshots/youtube_after.png"
        ]
        
        # Check if images exist
        existing_images = [img for img in images if os.path.exists(img)]
        if not existing_images:
            print("⚠️  No sample images found, testing with text only")
            existing_images = None
        
        messages = [
            {"role": "system", "content": "You are an expert web navigation evaluator."},
            caller.format_multimodal_message(text, existing_images)
        ]
        
        response = caller.call_multimodal(messages)
        result = caller.extract_json_from_response(response)
        
        print("✅ Multimodal call successful!")
        print(f"   Result: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Multimodal call failed: {e}")
        return False

def test_integration_function():
    """Test the call_qwen_vl integration function"""
    
    print("\n🔗 Testing Integration Function...")
    
    try:
        sys_prompt = "You are an expert evaluator."
        user_prompt = "Evaluate if the YouTube video click task was successful."
        
        parameters = {
            "task": "click_second_video",
            "platform": "youtube"
        }
        
        output_format = {
            "success": "boolean",
            "score": "float 0-1", 
            "confidence": "float 0-1",
            "reasoning": "string"
        }
        
        images = ["Sample Data-Screenshots/youtube_before.png", "Sample Data-Screenshots/youtube_after.png"]
        existing_images = [img for img in images if os.path.exists(img)]
        
        raw_text, json_result = call_qwen_vl(
            sys_prompt, user_prompt, parameters, output_format, existing_images
        )
        
        print("✅ Integration function successful!")
        print(f"   JSON Result: {json_result}")
        return True
        
    except Exception as e:
        print(f"❌ Integration function failed: {e}")
        return False

def main():
    """Main test runner"""
    
    # Setup check
    if not quick_test_setup():
        return
    
    # Run tests
    tests = [
        ("Basic Qwen-VL", test_qwen_vl_basic),
        ("Multimodal", test_qwen_vl_multimodal), 
        ("Integration Function", test_integration_function)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Your Qwen-VL framework is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")

if __name__ == "__main__":
    main()