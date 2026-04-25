"""
Accuracy tracking system for measuring AI response quality against ground truth.
Supports multiple accuracy metrics and evaluation frameworks.
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AccuracyMetric(Enum):
    """Types of accuracy metrics to track."""
    NUMERICAL_ACCURACY = "numerical_accuracy"
    CATEGORICAL_ACCURACY = "categorical_accuracy"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    COMPLETENESS = "completeness"
    RELEVANCE = "relevance"
    FACTUAL_CORRECTNESS = "factual_correctness"

@dataclass
class GroundTruthItem:
    """Ground truth data point for evaluation."""
    question: str
    expected_answer: str
    expected_data_points: List[str] = None
    expected_categories: List[str] = None
    expected_answer_pattern: str = None  # Pattern matching for questions
    numerical_tolerance: float = 0.01  # For numerical comparisons
    metadata: Dict[str, Any] = None

@dataclass
class AccuracyEvaluation:
    """Single accuracy evaluation result."""
    timestamp: datetime
    user_id: str
    agent_name: str
    question: str
    actual_answer: str
    ground_truth: GroundTruthItem
    accuracy_scores: Dict[str, float]
    overall_score: float
    evaluation_method: str
    metadata: Dict[str, Any] = None

class AccuracyTracker:
    """Centralized accuracy tracking and evaluation system."""
    
    def __init__(self):
        self.evaluations: List[AccuracyEvaluation] = []
        self.ground_truth_data: Dict[str, GroundTruthItem] = {}
        self.session_id = str(int(time.time()))
        
        # Load predefined ground truth data
        self._load_ground_truth_data()
    
    def _load_ground_truth_data(self):
        """Load predefined ground truth data for common questions."""
        # Financial calculations ground truth
        self.ground_truth_data.update({
            "savings_rate": GroundTruthItem(
                question="How can I improve my savings rate?",
                expected_answer="savings rate improvement recommendations",
                expected_answer_pattern="savings",
                expected_data_points=["net_savings", "income", "expenses"],
                numerical_tolerance=0.05
            ),
            "total_expenses": GroundTruthItem(
                question="What are my total expenses",
                expected_answer="total expense amount",
                expected_answer_pattern="total",
                expected_data_points=["expenses"],
                numerical_tolerance=0.01
            ),
            "income_summary": GroundTruthItem(
                question="How much income do I have",
                expected_answer="total income amount",
                expected_answer_pattern="income",
                expected_data_points=["total_income"],
                numerical_tolerance=0.01
            ),
            "savings_progress": GroundTruthItem(
                question="How am I doing with my savings goals",
                expected_answer="savings goals progress report",
                expected_answer_pattern="goals",
                expected_data_points=["savings_goals", "progress"],
                numerical_tolerance=0.05
            )
        })
    
    def add_ground_truth(self, question_id: str, ground_truth: GroundTruthItem):
        """Add new ground truth data point."""
        self.ground_truth_data[question_id] = ground_truth
    
    def evaluate_response(self, user_id: str, agent_name: str, question: str, 
                          actual_answer: str, context_data: Dict[str, Any] = None) -> AccuracyEvaluation:
        """Evaluate a response against ground truth."""
        # Find matching ground truth
        ground_truth = self._find_ground_truth(question)
        
        if not ground_truth:
            # Create a basic ground truth for unknown questions
            ground_truth = GroundTruthItem(
                question=question,
                expected_answer=actual_answer,  # Use actual as baseline
                expected_data_points=[],
                metadata={"auto_generated": True}
            )
        
        # Calculate accuracy scores
        accuracy_scores = self._calculate_accuracy_scores(actual_answer, ground_truth, context_data)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(accuracy_scores)
        
        # Create evaluation record
        evaluation = AccuracyEvaluation(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            agent_name=agent_name,
            question=question,
            actual_answer=actual_answer,
            ground_truth=ground_truth,
            accuracy_scores=accuracy_scores,
            overall_score=overall_score,
            evaluation_method="automated",
            metadata={"context_data": context_data} if context_data else {}
        )
        
        self.evaluations.append(evaluation)
        logger.info(f"Evaluated response for {agent_name}: overall accuracy {overall_score:.2f}")
        
        return evaluation
    
    def _find_ground_truth(self, question: str) -> Optional[GroundTruthItem]:
        """Find ground truth data for a given question."""
        question_lower = question.lower()
        
        # Direct match
        for gt_id, gt in self.ground_truth_data.items():
            if gt.question.lower() == question_lower:
                return gt
        
        # Pattern matching
        for gt_id, gt in self.ground_truth_data.items():
            if hasattr(gt, 'expected_answer_pattern'):
                pattern = gt.expected_answer_pattern.lower()
                if pattern in question_lower:
                    return gt
        
        # Keyword matching
        for gt_id, gt in self.ground_truth_data.items():
            if any(keyword in question_lower for keyword in gt.question.lower().split()):
                return gt
        
        return None
    
    def _calculate_accuracy_scores(self, actual_answer: str, ground_truth: GroundTruthItem, 
                                  context_data: Dict[str, Any] = None) -> Dict[str, float]:
        """Calculate various accuracy metrics."""
        scores = {}
        
        # Numerical accuracy
        scores[AccuracyMetric.NUMERICAL_ACCURACY.value] = self._calculate_numerical_accuracy(
            actual_answer, ground_truth, context_data
        )
        
        # Data completeness
        scores[AccuracyMetric.COMPLETENESS.value] = self._calculate_completeness(
            actual_answer, ground_truth, context_data
        )
        
        # Relevance
        scores[AccuracyMetric.RELEVANCE.value] = self._calculate_relevance(
            actual_answer, ground_truth
        )
        
        # Factual correctness (basic)
        scores[AccuracyMetric.FACTUAL_CORRECTNESS.value] = self._calculate_factual_correctness(
            actual_answer, ground_truth, context_data
        )
        
        return scores
    
    def _calculate_numerical_accuracy(self, actual_answer: str, ground_truth: GroundTruthItem,
                                     context_data: Dict[str, Any] = None) -> float:
        """Calculate numerical accuracy based on context data."""
        if not context_data or not ground_truth.expected_data_points:
            return 0.5  # Neutral score if no data to compare
        
        # Extract numbers from actual answer
        actual_numbers = self._extract_numbers(actual_answer)
        
        # Extract expected numbers from context
        expected_numbers = []
        for data_point in ground_truth.expected_data_points:
            if data_point in context_data:
                value = context_data[data_point]
                if isinstance(value, (int, float)):
                    expected_numbers.append(float(value))
        
        if not expected_numbers or not actual_numbers:
            return 0.5
        
        # Compare numbers (simple approach: check if any actual number is close to expected)
        best_match = 0.0
        for actual_num in actual_numbers:
            for expected_num in expected_numbers:
                tolerance = ground_truth.numerical_tolerance
                if abs(actual_num - expected_num) / max(abs(expected_num), 1) <= tolerance:
                    best_match = max(best_match, 1.0 - abs(actual_num - expected_num) / max(abs(expected_num), 1))
        
        return best_match
    
    def _calculate_completeness(self, actual_answer: str, ground_truth: GroundTruthItem,
                               context_data: Dict[str, Any] = None) -> float:
        """Calculate completeness based on expected data points."""
        if not ground_truth.expected_data_points:
            return 0.8  # Good score if no specific requirements
        
        mentioned_data_points = 0
        for data_point in ground_truth.expected_data_points:
            if data_point.lower() in actual_answer.lower():
                mentioned_data_points += 1
        
        return mentioned_data_points / len(ground_truth.expected_data_points)
    
    def _calculate_relevance(self, actual_answer: str, ground_truth: GroundTruthItem) -> float:
        """Calculate relevance score based on answer content."""
        # Simple keyword-based relevance
        question_keywords = set(ground_truth.question.lower().split())
        answer_keywords = set(actual_answer.lower().split())
        
        # Calculate overlap
        overlap = len(question_keywords.intersection(answer_keywords))
        total_keywords = len(question_keywords)
        
        if total_keywords == 0:
            return 0.5
        
        return min(overlap / total_keywords, 1.0)
    
    def _calculate_factual_correctness(self, actual_answer: str, ground_truth: GroundTruthItem,
                                       context_data: Dict[str, Any] = None) -> float:
        """Calculate basic factual correctness."""
        # This is a simplified implementation
        # In practice, this could use more sophisticated NLP techniques
        
        # Check for obvious factual errors
        error_indicators = ["i don't know", "unable to", "cannot", "error", "failed"]
        error_count = sum(1 for indicator in error_indicators if indicator in actual_answer.lower())
        
        # Penalize error indicators
        base_score = 1.0
        penalty = error_count * 0.2
        
        return max(0.0, base_score - penalty)
    
    def _calculate_overall_score(self, accuracy_scores: Dict[str, float]) -> float:
        """Calculate overall accuracy score from individual metrics."""
        if not accuracy_scores:
            return 0.0
        
        # Weighted average of different metrics
        weights = {
            AccuracyMetric.NUMERICAL_ACCURACY.value: 0.3,
            AccuracyMetric.COMPLETENESS.value: 0.2,
            AccuracyMetric.RELEVANCE.value: 0.3,
            AccuracyMetric.FACTUAL_CORRECTNESS.value: 0.2
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric, score in accuracy_scores.items():
            weight = weights.get(metric, 0.25)  # Default weight
            weighted_sum += score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _extract_numbers(self, text: str) -> List[float]:
        """Extract numbers from text."""
        import re
        # Find numbers (including decimals and currency)
        patterns = [
            r'\$?(\d+(?:,\d{3})*(?:\.\d+)?)',  # Currency and regular numbers
            r'(\d+(?:\.\d+)?)',  # Simple decimals
        ]
        
        numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    # Remove commas and convert to float
                    clean_num = match.replace(',', '')
                    numbers.append(float(clean_num))
                except ValueError:
                    continue
        
        return numbers
    
    def get_accuracy_summary(self, user_id: str = None, agent_name: str = None,
                           period_hours: int = 24) -> Dict[str, Any]:
        """Get accuracy summary statistics."""
        start_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)
        end_time = datetime.now(timezone.utc)
        
        # Filter evaluations
        relevant_evals = [
            eval for eval in self.evaluations
            if eval.timestamp >= start_time and eval.timestamp <= end_time
        ]
        
        if user_id:
            relevant_evals = [e for e in relevant_evals if e.user_id == user_id]
        
        if agent_name:
            relevant_evals = [e for e in relevant_evals if e.agent_name == agent_name]
        
        if not relevant_evals:
            return {
                "total_evaluations": 0,
                "average_accuracy": 0.0,
                "accuracy_distribution": {},
                "metric_breakdown": {},
                "period_hours": period_hours
            }
        
        # Calculate statistics
        overall_scores = [e.overall_score for e in relevant_evals]
        avg_accuracy = sum(overall_scores) / len(overall_scores)
        
        # Accuracy distribution
        distribution = {
            "excellent": len([s for s in overall_scores if s >= 0.9]),
            "good": len([s for s in overall_scores if 0.7 <= s < 0.9]),
            "fair": len([s for s in overall_scores if 0.5 <= s < 0.7]),
            "poor": len([s for s in overall_scores if s < 0.5])
        }
        
        # Metric breakdown
        metric_breakdown = {}
        for metric in AccuracyMetric:
            scores = [e.accuracy_scores.get(metric.value, 0) for e in relevant_evals]
            if scores:
                metric_breakdown[metric.value] = {
                    "average": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores)
                }
        
        return {
            "total_evaluations": len(relevant_evals),
            "average_accuracy": avg_accuracy,
            "accuracy_distribution": distribution,
            "metric_breakdown": metric_breakdown,
            "period_hours": period_hours
        }
    
    def get_accuracy_trends(self, user_id: str = None, agent_name: str = None,
                           period_hours: int = 24, interval: str = "hour") -> List[Dict]:
        """Get accuracy trends over time."""
        start_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)
        end_time = datetime.now(timezone.utc)
        
        # Filter evaluations
        relevant_evals = [
            eval for eval in self.evaluations
            if eval.timestamp >= start_time and eval.timestamp <= end_time
        ]
        
        if user_id:
            relevant_evals = [e for e in relevant_evals if e.user_id == user_id]
        
        if agent_name:
            relevant_evals = [e for e in relevant_evals if e.agent_name == agent_name]
        
        # Group by time intervals
        time_buckets = self._create_time_buckets(start_time, end_time, interval)
        trends = []
        
        for bucket_start, bucket_end in time_buckets:
            bucket_evals = [e for e in relevant_evals 
                          if bucket_start <= e.timestamp < bucket_end]
            
            if bucket_evals:
                avg_score = sum(e.overall_score for e in bucket_evals) / len(bucket_evals)
                trends.append({
                    "timestamp": bucket_start.isoformat(),
                    "average_accuracy": avg_score,
                    "evaluation_count": len(bucket_evals)
                })
        
        return trends
    
    def _create_time_buckets(self, start_time: datetime, end_time: datetime,
                           interval: str) -> List[tuple]:
        """Create time buckets for trend analysis."""
        buckets = []
        current = start_time
        
        if interval == "minute":
            delta = timedelta(minutes=1)
        elif interval == "hour":
            delta = timedelta(hours=1)
        elif interval == "day":
            delta = timedelta(days=1)
        else:
            delta = timedelta(hours=1)
        
        while current < end_time:
            buckets.append((current, current + delta))
            current += delta
        
        return buckets

# Global accuracy tracker instance
accuracy_tracker = AccuracyTracker()
