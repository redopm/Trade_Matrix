"""
PatternLabel ORM Model — Phase 2
Stores labeled chart patterns (from Gemini Vision or manual labeling).
Used as training data for the local ML classifier.
"""
import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.database import Base


class LabelSource(str, enum.Enum):
    GEMINI = "gemini"
    RULE_BASED = "rule_based"
    MANUAL = "manual"


class PatternLabel(Base):
    """
    Stores labeled chart windows for ML training.
    Each row = one 60-day chart window + its pattern label.
    """
    __tablename__ = "pattern_labels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    label_date = Column(String(10), nullable=False)           # YYYY-MM-DD (last day of window)
    window_start = Column(String(10))                          # YYYY-MM-DD
    window_end = Column(String(10))                            # YYYY-MM-DD
    window_days = Column(Integer, default=60)

    # Pattern Info
    pattern_name = Column(String(50), nullable=False, index=True)  # e.g. "double_bottom"
    pattern_confidence = Column(Float, default=1.0)                # 0.0 - 1.0
    is_bullish = Column(Boolean, default=True)
    is_valid = Column(Boolean, default=True)                        # For filtering bad labels

    # Gemini response
    label_source = Column(String(20), default=LabelSource.GEMINI)
    gemini_raw_response = Column(Text)                              # Full Gemini JSON response
    gemini_reasoning = Column(Text)                                 # Gemini's explanation

    # Chart image
    chart_image_path = Column(String(500))                          # Path to saved PNG

    # Extracted features (stored as JSON string)
    features_json = Column(Text)                                    # 23 geometric features

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<PatternLabel {self.symbol} {self.pattern_name} ({self.label_date})>"


class PatternDetection(Base):
    """
    Stores real-time pattern detections (output of the trained model).
    Linked to screener signals for confluence scoring.
    """
    __tablename__ = "pattern_detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, nullable=True, index=True)     # FK to ScreenerSignal
    symbol = Column(String(20), nullable=False, index=True)
    detection_date = Column(String(10), nullable=False)

    # Detection Results
    pattern_name = Column(String(50))                          # Top pattern detected
    pattern_confidence = Column(Float)                         # 0.0 - 1.0
    is_bullish = Column(Boolean)
    is_confluence = Column(Boolean, default=False)             # Phase1 + Phase2 both pass

    # All pattern scores (JSON)
    all_scores_json = Column(Text)                             # {pattern: score, ...}

    # Chart
    chart_image_path = Column(String(500))

    # Features used
    features_json = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<PatternDetection {self.symbol} {self.pattern_name} {self.pattern_confidence:.2f}>"
