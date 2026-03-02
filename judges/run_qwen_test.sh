#!/bin/bash
# Helper script to run the Qwen API evaluation test

echo "🚀 Starting Evaluation Pipeline Test with Qwen API"
echo "=================================================="
echo ""

# Check if DASHSCOPE_API_KEY is set
if [ -z "$DASHSCOPE_API_KEY_SIN" ]; then
    echo "⚠️  DASHSCOPE_API_KEY not set"
    echo ""
    echo "To test with real Qwen API, set your API key:"
    echo "  export DASHSCOPE_API_KEY='your_api_key_here'"
    echo ""
    echo "Running in MOCK mode for demonstration..."
    echo ""
fi

# Run the test
cd "$(dirname "$0")"
python test_evaluation_with_qwen.py

echo ""
echo "=================================================="
echo "✅ Test execution completed"
