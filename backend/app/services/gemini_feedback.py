"""
Gemini Feedback Loop — Self-Learning Phase
Sends pattern performance data to Gemini to get recommendations on tightening/relaxing detection rules.
Writes recommendations to feedback_config.json.
"""
import json
import os
from pathlib import Path
from typing import Optional
import google.generativeai as genai

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

FEEDBACK_FILE = Path(__file__).resolve().parent.parent.parent / "database" / "feedback_config.json"

class GeminiFeedbackLoop:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)
        else:
            self.model = None
            logger.warning("No GEMINI_API_KEY found. Feedback loop will be disabled.")

    async def run_feedback_loop(self, pattern_performance: list[dict]) -> Optional[dict]:
        """
        Takes pattern performance stats and asks Gemini for rule adjustments.
        """
        if not self.model:
            logger.error("Feedback loop cannot run without Gemini API Key.")
            return None

        # Filter patterns that have enough data
        valid_stats = [p for p in pattern_performance if (p.get("winners", 0) + p.get("losers", 0)) >= 3]
        if not valid_stats:
            logger.info("Not enough pattern outcome data to run feedback loop.")
            return None

        logger.info(f"Running Gemini Feedback Loop on {len(valid_stats)} patterns...")

        prompt = f"""
        You are an expert quantitative trading AI engineer.
        We have a rule-based chart pattern detection system. We are tracking the real-world performance of these patterns.
        A pattern is a WINNER if the price hits the 12% profit target before the 2xATR stop loss.
        A pattern is a LOSER if it hits the stop loss first.

        Here is the recent performance data of our patterns:
        {json.dumps(valid_stats, indent=2)}

        Our current default geometric thresholds are:
        - peak_prominence_pct: 0.03 (Peaks must stand out by at least 3% of the chart's price range)
        - peak_distance_days: 5 (Peaks must be at least 5 days apart)
        - neckline_tolerance_pct: 0.02 (Necklines can be angled by up to 2%)

        Task:
        For patterns with a win rate BELOW 50%, suggest tightening the thresholds (e.g., higher prominence, longer distance, stricter neckline).
        For patterns with a win rate ABOVE 70%, suggest slightly relaxing the thresholds to capture more opportunities.
        For patterns between 50-70%, keep them at defaults.

        Return ONLY a JSON object containing the suggested overrides per pattern. Use this exact format:
        {{
            "overrides": {{
                "double_top": {{
                    "peak_prominence_pct": 0.04,
                    "peak_distance_days": 7
                }}
            }},
            "reasoning": "Brief explanation of why you made these changes."
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            text = response.text
            
            # Clean Markdown formatting if present
            if text.startswith("```json"):
                text = text.replace("```json", "", 1)
            if text.startswith("```"):
                text = text.replace("```", "", 1)
            if text.endswith("```"):
                text = text[:-3]
            
            text = text.strip()
            new_config = json.loads(text)
            
            # Save to JSON file
            FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(FEEDBACK_FILE, "w") as f:
                json.dump(new_config, f, indent=4)
                
            logger.info(f"Successfully updated feedback config: {new_config.get('reasoning')}")
            return new_config
            
        except Exception as e:
            logger.error(f"Gemini Feedback Loop failed: {e}")
            return None

    @staticmethod
    def load_feedback_config() -> dict:
        """Loads the current feedback config overrides."""
        if FEEDBACK_FILE.exists():
            try:
                with open(FEEDBACK_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load feedback config: {e}")
        return {"overrides": {}}
