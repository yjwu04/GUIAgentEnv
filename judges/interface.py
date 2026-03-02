# Try using the following interface
from evaluation_pipeline import EvaluationPipeline
from agents.agent_base import AgentStepResult
from base_judge import JudgeResult
agent_flow_output = [AgentStepResult(task1),AgentStepResult(task2)]#...]
batch_data = agent_flow_output
eval = EvaluationPipeline()
result = eval.batch_evaluate(agent_flow_output)#array
#result[task_id-1]["task_id"] get JudgeResult
'''
    score_name: str # e.g., degradation_score
    score: float
    reason: str
    confidence: float # from 0-1 
    additional_info: Dict[str, Any]
'''