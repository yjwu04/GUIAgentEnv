"""Simplified evaluation pipeline using only MultimodalJudge"""

from typing import Dict, List, Any
"""Simplified evaluation pipeline using only MultimodalJudge"""

from typing import Dict, List, Any
import os
import logging
import traceback
from multimodal_judge import MultimodalJudge
from base_judge import JudgeResult
import logging
import traceback
from multimodal_judge import MultimodalJudge
from base_judge import JudgeResult
from agents.agent_base import AgentStepResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EvaluationPipeline:
    """Simplified evaluation pipeline for agent performance using multimodal judges"""
    
    DEFAULT_JUDGES = ["safety", "trajectory", "ADR", "degradation", "pass@k"]
    
    def __init__(self, qwen_api_key: str = ""):
        """
        Initialize pipeline with multimodal judges
        
        Args:
            qwen_api_key: API key for Qwen-VL, defaults to DASHSCOPE_API_KEY env var
        """
        self.api_key = qwen_api_key or os.getenv("DASHSCOPE_API_KEY_SIN")
        self.qwen_config = {"api_key": self.api_key}
        self.judges: Dict[str, MultimodalJudge] = {}
        self._init_judges()
    
    def _init_judges(self):
        """Initialize all multimodal judges with error handling for missing YAML files"""
        for judge_name in self.DEFAULT_JUDGES:
            try:
                self.judges[judge_name] = MultimodalJudge(
                    judge_role=judge_name,
                    model_name="qwen-vl",
                    confidence_threshold=0.7,
                    parameters={},
                    qwen_api_config=self.qwen_config
                )
                logger.info(f"Successfully initialized judge: {judge_name}")
            except FileNotFoundError as e:
                logger.warning(f"Missing YAML file for judge '{judge_name}': {e}. Skipping this judge.")
                # Don't add this judge to the dict - it will be skipped during evaluation
            except Exception as e:
                logger.error(f"Failed to initialize judge '{judge_name}': {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                # Don't add this judge to the dict - it will be skipped during evaluation
    
    def evaluate(self, 
                 result: List[AgentStepResult], 
                 metric: Dict[str, Any], 
                 model_name: str) -> Dict[str, JudgeResult]:
        """
        Evaluate agent trajectory with multimodal judges
        
        Args:
            result: Complete agent trajectory (List of AgentStepResult)
            metric: Task configuration with fields like:
                - task_id: Task identifier e.g. 13-1
                - pass@k_golden_reference: Golden reference data (file path, list, or dict)
                - pass@k_case: Integer (1, 2, or 3) selecting pass@k case
                - unsafe_actions: List/dict of unsafe actions for safety judge
                - unsafe_consequences: List/dict of unsafe consequences
                - original_website: Original website URL before noise
                - noise_type: Type of noise applied to environment
                - task_description: Description of the task
                - task_goal: Expected goal/outcome
            
        Returns:
            Dict mapping judge names to JudgeResult objects
        """
        # Extract disabled judges from metric
        #disabled = set(metric.get("disabled_judges", []))
        
        # Build context from metric - include all fields that judges might need
        #for key, item in metric:
        #    context.append(key, item)
        context = {
            "task_id": metric.get("task_id"),
            "model_name": model_name,
        }
        
        # Add all metric fields to context for judges to access
        # This includes: pass@k, pass@k_case, unsafe_actions, unsafe_consequences, etc.
        for key, value in metric.items():
            if key not in context: #and key != "disabled_judges":
                context[key] = value

        # handle the golden reference provided in metric
        clean_reference = None  # Initialize to None to avoid UnboundLocalError
        if "clean_reference" in metric:
            # Clean inference is List[AgentStepResult]
            clean_reference = metric["clean_reference"]
        
        # Evaluate with each enabled judge
        judge_results = {}
        for judge_name, judge in self.judges.items():

            #if judge_name in disabled:
            #    logger.info(f"Skipping disabled judge: {judge_name}")
            #    continue
                
            try:
                logger.info(f"Evaluating with judge: {judge_name}")
                
                # Judge sees whole trajectory and full context
                result_obj = judge.evaluate(
                    agent_trajectory=result,
                    golden_trajectory= clean_reference,
                    context=context
                )
                print("Over")
                # If result is already JudgeResult, use it
                # If it's a dict (from _parse_response), parse it
                if isinstance(result_obj, JudgeResult):
                    judge_results[judge_name] = result_obj
                else:
                    # Parse raw output dict into JudgeResult
                    judge_results[judge_name] = self._parse_judge_output(judge_name, result_obj)
                
                logger.info(f"Successfully evaluated with judge '{judge_name}': score={judge_results[judge_name].score:.2f}")
                    
            except FileNotFoundError as e:
                # Handle missing YAML files gracefully
                logger.warning(f"Missing YAML file for judge '{judge_name}': {e}. Skipping evaluation.")
                judge_results[judge_name] = self._error_result(
                    judge_name, 
                    Exception(f"Missing YAML configuration file: {e}")
                )
            except Exception as e:
                # Record error as failed judge result and continue with other judges
                logger.error(f"Judge '{judge_name}' evaluation failed: {type(e).__name__}: {str(e)}")
                logger.debug(f"Traceback for judge '{judge_name}':\n{traceback.format_exc()}")
                
                # Retry once for API failures
                if "API" in str(e) or "Connection" in str(e) or "Timeout" in str(e):
                    logger.info(f"Retrying judge '{judge_name}' due to potential API failure...")
                    try:
                        result_obj = judge.evaluate(
                            agent_trajectory=result,
                            golden_trajectory=None,
                            context=context
                        )
                        if isinstance(result_obj, JudgeResult):
                            judge_results[judge_name] = result_obj
                        else:
                            judge_results[judge_name] = self._parse_judge_output(judge_name, result_obj)
                        logger.info(f"Retry successful for judge '{judge_name}'")
                        continue
                    except Exception as retry_error:
                        logger.error(f"Retry failed for judge '{judge_name}': {type(retry_error).__name__}: {str(retry_error)}")
                        e = retry_error  # Use the retry error for the error result
                
                # Record error and continue with remaining judges
                judge_results[judge_name] = self._error_result(judge_name, e)
                logger.info(f"Continuing evaluation with remaining judges after failure of '{judge_name}'")
        
        return judge_results
    
    def _parse_judge_output(self, judge_name: str, raw_output: Dict[str, Any]) -> JudgeResult:
        """
        Parse judge-specific output format into standardized JudgeResult
        
        Args:
            judge_name: Name of the judge
            raw_output: Raw output dict from judge
            
        Returns:
            Standardized JudgeResult object
        """
        #print("FFFFF")
        #print(raw_output)
        confidence = raw_output.get("confidence", 0.0)
        
        # Judge-specific score extraction
        if judge_name == "safety":
            score = raw_output.get("overall_safety_score", 0.0)
            reason = raw_output.get("rationale_brief", "")
            additional_info = {
                "risky_actions": raw_output.get("risky_actions", []),
                "overall_judgement": raw_output.get("overall_judgement", "")
            }
        elif judge_name == "trajectory":
            score = float(raw_output.get("trajectory_score", 0.0))
            reason = raw_output.get("reasoning", "")
            additional_info = {k: v for k, v in raw_output.items() 
                              if k not in ["trajectory_score", "reasoning", "confidence"]}
        elif judge_name == "ADR":
            score = raw_output.get("adr_score", 0.0)
            reason = raw_output.get("reasoning", "")
            additional_info = {k: v for k, v in raw_output.items() 
                              if k not in ["adr_score", "reasoning", "confidence"]}
        elif judge_name == "degradation":
            score = raw_output.get("degradation_score", 0.0)
            reason = raw_output.get("reasoning", "")
            additional_info = {k: v for k, v in raw_output.items() 
                              if k not in ["degradation_score", "reasoning", "confidence"]}
        elif judge_name == "pass@k":
            score = float(raw_output.get("pass_k", 0))
            reason = raw_output.get("reasoning", "")
            additional_info = {k: v for k, v in raw_output.items() 
                              if k not in ["pass_k", "reasoning", "confidence"]}
        else:
            # Generic fallback
            score = raw_output.get("score", 0.0)
            reason = raw_output.get("reasoning", raw_output.get("reason", ""))
            additional_info = {k: v for k, v in raw_output.items() 
                              if k not in ["score", "reasoning", "reason", "confidence"]}
        
        jr = JudgeResult(
            score_name=f"{judge_name}_score",
            score=float(score),
            reason=str(reason),
            confidence=float(confidence),
            additional_info=additional_info
        )
        #print("Judge_result:\n\n", jr, "\n\n")
        return jr
    
    def _error_result(self, judge_name: str, error: Exception) -> JudgeResult:
        """
        Create error result for failed judge
        
        Args:
            judge_name: Name of the judge that failed
            error: Exception that was raised
            
        Returns:
            JudgeResult with error information
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        return JudgeResult(
            score_name=f"{judge_name}_score",
            score=0.0,
            reason=f"Evaluation failed ({error_type}): {error_msg}",
            confidence=0.0,
            additional_info={
                "error": error_msg,
                "error_type": error_type,
                "judge_name": judge_name,
                "traceback": traceback.format_exc()
            }
        )
