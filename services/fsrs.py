import math
from datetime import datetime, timedelta, timezone


class FSRSScheduler:
    def __init__(self):
        # Default weights/learning rates
        self.weights = [0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01, 1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61]

    def calculate_retrievability(self, t: float, s: float) -> float:
        """
        Calculates R based on the formula from the proposal.
        """
        # LaTeX formula: R = e^(ln(0.9) * (t / s))
        # Where t is time since last review (in days), s is memory stability
        if s == 0:
            return 0.0
        return math.exp(math.log(0.9) * (t / s))

    def update_memory_state(self, current_stability: float, difficulty: float, grade: int, time_since_review_days: float) -> float:
        """
        Calculates new stability based on recall grade (1=Again, 2=Hard, 3=Good, 4=Easy).
        """
        # Simplified placeholder for the full S_{n+1} matrix math
        # In reality, this applies: S_{n+1} = S_n * (1 + a * e^(-b*d) * (h-1) * e^(c*S_n))
        
        if grade == 1: # Failed
            return max(0.1, current_stability * 0.3)
            
        a, b, c = 0.4, 0.6, 2.4 # Simplified infered rates
        h = grade - 1 # Recall grade adjustment
        
        new_stability = current_stability * (1 + a * math.exp(-b * difficulty) * h * math.exp(c * current_stability))
        return new_stability

    def calculate_next_review(self, card, grade: int) -> datetime:
        now = datetime.now(timezone.utc)
        
        if not card.last_review:
            t = 0
        else:
            t = (now - card.last_review).total_seconds() / 86400.0

        new_stability = self.update_memory_state(card.stability, card.difficulty, grade, t)
        
        # Determine interval (days) to hit 90% retrievability
        interval = new_stability * (math.log(0.9) / math.log(0.9)) # Simplified to interval = stability
        
        return now + timedelta(days=interval)