# Code Reference: Top 10 AI Analysis Changes

## File-by-File Changes

---

## 1. config/scoring_config.py

### Added Constants
```python
# AI Analysis Configuration
TOP_AI_ANALYSIS_COUNT = 10  # Number of top-ranked influencers to receive Gemini AI analysis
```

### Updated ScoringConfig Dataclass
```python
@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """..."""
    language_weight: float = LANGUAGE_WEIGHT
    niche_weight: float = NICHE_WEIGHT
    follower_weight: float = FOLLOWER_WEIGHT
    bio_weight: float = BIO_WEIGHT
    engagement_weight: float = ENGAGEMENT_WEIGHT
    ai_weight: float = AI_WEIGHT
    target_languages: tuple[str, ...] = TARGET_LANGUAGES
    target_niches: tuple[str, ...] = TARGET_NICHES
    bio_keywords: tuple[str, ...] = BIO_KEYWORDS
    follower_cap: float = FOLLOWER_CAP
    engagement_rate_cap: float = ENGAGEMENT_RATE_CAP
    top_ai_analysis_count: int = TOP_AI_ANALYSIS_COUNT  # ← NEW FIELD
```

### Updated Validation
```python
def __post_init__(self) -> None:
    """..."""
    # ... existing validation ...
    
    if self.top_ai_analysis_count < 0:  # ← NEW VALIDATION
        raise ValueError("top_ai_analysis_count cannot be negative")
```

---

## 2. models/score_result.py

### Updated ScoreResult Dataclass
```python
@dataclass(slots=True)
class ScoreResult:
    """..."""
    total_score: float
    preliminary_score: float = 0.0  # ← NEW FIELD (rule-based only)
    score_breakdown: dict[str, float] = field(default_factory=dict)
    matched_languages: list[str] = field(default_factory=list)
    matched_niches: list[str] = field(default_factory=list)
    remarks: list[str] = field(default_factory=list)
```

---

## 3. models/evaluated_influencer.py

### Updated EvaluatedInfluencer Dataclass
```python
@dataclass(slots=True)
class EvaluatedInfluencer:
    """Bundle the influencer, AI analysis, and scoring output together."""
    influencer: Influencer
    ai_analysis: AIAnalysis
    score_result: ScoreResult
    rank: int = 0
    ai_analysis_performed: bool = False  # ← NEW FIELD
```

---

## 4. services/scoring_service.py

### New Method: score_preliminary()
```python
def score_preliminary(self, influencer: Influencer) -> ScoreResult:
    """Return rule-based score without AI analysis (for initial ranking).
    
    This method computes a preliminary score using only rule-based criteria:
    - Language match
    - Niche keywords
    - Bio relevance
    - Follower count
    - Engagement (if available)
    
    AI score is set to 0 and not included in the total.
    This allows quick ranking of large datasets before expensive Gemini calls.
    """
    language_score, matched_languages, language_remarks = self._score_language(influencer)
    niche_score, matched_niches, niche_remarks = self._score_niche(influencer)
    bio_score, bio_remarks = self._score_bio(influencer)
    follower_score, follower_remarks = self._score_followers(influencer)
    engagement_score, engagement_remarks = self._score_engagement(influencer)

    # Do NOT include AI weight in preliminary scoring
    preliminary_weight = (
        self._config.language_weight
        + self._config.niche_weight
        + self._config.bio_weight
        + self._config.follower_weight
        + self._config.engagement_weight
    )

    score_breakdown = {
        "language": self._weighted_contribution(language_score, self._config.language_weight, preliminary_weight),
        "niche": self._weighted_contribution(niche_score, self._config.niche_weight, preliminary_weight),
        "bio": self._weighted_contribution(bio_score, self._config.bio_weight, preliminary_weight),
        "followers": self._weighted_contribution(follower_score, self._config.follower_weight, preliminary_weight),
        "engagement": self._weighted_contribution(engagement_score, self._config.engagement_weight, preliminary_weight),
    }

    total_score = round(sum(score_breakdown.values()), 2)
    remarks = [
        *language_remarks,
        *niche_remarks,
        *bio_remarks,
        *follower_remarks,
        *engagement_remarks,
        "Preliminary rule-based score; AI analysis pending.",
    ]

    return ScoreResult(
        total_score=total_score,
        preliminary_score=total_score,
        score_breakdown=score_breakdown,
        matched_languages=matched_languages,
        matched_niches=matched_niches,
        remarks=remarks,
    )
```

### Updated Method: score()
```python
def score(self, influencer: Influencer, ai_analysis: AIAnalysis | None = None) -> ScoreResult:
    """Return the weighted score result for one influencer."""
    language_score, matched_languages, language_remarks = self._score_language(influencer)
    niche_score, matched_niches, niche_remarks = self._score_niche(influencer)
    bio_score, bio_remarks = self._score_bio(influencer)
    follower_score, follower_remarks = self._score_followers(influencer)
    engagement_score, engagement_remarks = self._score_engagement(influencer)
    ai_score, ai_remarks = self._score_ai_orientation(influencer, ai_analysis)

    total_weight = self._config.total_weight
    score_breakdown = {
        "language": self._weighted_contribution(language_score, self._config.language_weight, total_weight),
        "niche": self._weighted_contribution(niche_score, self._config.niche_weight, total_weight),
        "bio": self._weighted_contribution(bio_score, self._config.bio_weight, total_weight),
        "followers": self._weighted_contribution(follower_score, self._config.follower_weight, total_weight),
        "engagement": self._weighted_contribution(engagement_score, self._config.engagement_weight, total_weight),
        "ai_orientation": self._weighted_contribution(ai_score, self._config.ai_weight, total_weight),
    }

    total_score = round(sum(score_breakdown.values()), 2)
    remarks = [
        *language_remarks,
        *niche_remarks,
        *bio_remarks,
        *follower_remarks,
        *engagement_remarks,
        *ai_remarks,
    ]

    # ← Calculate preliminary score (without AI component)
    preliminary_score = self._calculate_preliminary_score(
        language_score, matched_languages, matched_niches, niche_score, bio_score, follower_score, engagement_score
    )

    return ScoreResult(
        total_score=total_score,
        preliminary_score=preliminary_score,  # ← NEW FIELD
        score_breakdown=score_breakdown,
        matched_languages=matched_languages,
        matched_niches=matched_niches,
        remarks=remarks,
    )
```

### New Helper Method: _calculate_preliminary_score()
```python
def _calculate_preliminary_score(
    self,
    language_score: float,
    matched_languages: list[str],
    matched_niches: list[str],
    niche_score: float,
    bio_score: float,
    follower_score: float,
    engagement_score: float,
) -> float:
    """Calculate rule-based preliminary score without AI component.
    
    This is used for the initial ranking before Gemini calls.
    """
    preliminary_weight = (
        self._config.language_weight
        + self._config.niche_weight
        + self._config.bio_weight
        + self._config.follower_weight
        + self._config.engagement_weight
    )

    score_breakdown = {
        "language": self._weighted_contribution(language_score, self._config.language_weight, preliminary_weight),
        "niche": self._weighted_contribution(niche_score, self._config.niche_weight, preliminary_weight),
        "bio": self._weighted_contribution(bio_score, self._config.bio_weight, preliminary_weight),
        "followers": self._weighted_contribution(follower_score, self._config.follower_weight, preliminary_weight),
        "engagement": self._weighted_contribution(engagement_score, self._config.engagement_weight, preliminary_weight),
    }

    return round(sum(score_breakdown.values()), 2)
```

---

## 5. services/dashboard_service.py

### Refactored Method: evaluate_influencers()
```python
def evaluate_influencers(self, influencers: Sequence[Influencer]) -> list[EvaluatedInfluencer]:
    """Analyze and score influencers using a two-tier approach.
    
    Workflow:
    1. Compute preliminary rule-based scores for ALL influencers.
    2. Sort by preliminary score and select the Top N for AI analysis.
    3. Call Gemini only on the Top N influencers.
    4. Re-score the Top N with their AI analysis results.
    5. Leave the remaining influencers with preliminary scores only.
    6. Return all results ranked by final total score.
    """
    if not influencers:
        return []

    logger.info("Evaluating %d influencers (two-tier approach)", len(influencers))

    # Step 1: Score all influencers with preliminary (rule-based only) scores
    logger.info("Step 1: Computing preliminary rule-based scores for all %d influencers", len(influencers))
    preliminary_evaluations = [
        self._evaluate_preliminary(influencer) for influencer in influencers
    ]

    # Step 2: Sort by preliminary score and select Top N
    config = self.scoring_service._config
    top_n = max(1, config.top_ai_analysis_count)
    sorted_by_preliminary = sorted(
        preliminary_evaluations,
        key=lambda item: (
            -item.score_result.preliminary_score,
            -item.influencer.followers,
            item.influencer.name.casefold(),
        ),
    )
    
    top_influencers = sorted_by_preliminary[:top_n]
    remaining_influencers = sorted_by_preliminary[top_n:]

    logger.info("Step 2: Selected Top %d influencers for AI analysis (out of %d)", len(top_influencers), len(influencers))

    # Step 3 & 4: Analyze Top N with Gemini and re-score
    logger.info("Step 3-4: Analyzing Top %d influencers with Gemini", len(top_influencers))
    top_influencer_objects = [eval_result.influencer for eval_result in top_influencers]
    ai_analysis_map = self._analyze_influencers(top_influencer_objects)

    top_with_ai = [
        self._evaluate_with_ai(
            eval_result.influencer,
            ai_analysis_map.get(self._normalize_handle(eval_result.influencer.handle)),
            ai_analysis_performed=True,
        )
        for eval_result in top_influencers
    ]

    # Step 5: Keep remaining with preliminary scores (no AI analysis)
    logger.info("Step 5: Keeping remaining %d influencers with preliminary scores only", len(remaining_influencers))
    remaining_with_no_ai = [
        self._evaluate_with_ai(
            eval_result.influencer,
            self._not_analyzed_fallback(eval_result.influencer),
            ai_analysis_performed=False,
        )
        for eval_result in remaining_influencers
    ]

    # Step 6: Merge and rank all results
    all_evaluated = top_with_ai + remaining_with_no_ai
    ranked_influencers = self._rank_evaluations(all_evaluated)

    logger.info(
        "Finished evaluating %d influencers (Top %d analyzed with AI, %d with preliminary scores only)",
        len(ranked_influencers),
        len(top_with_ai),
        len(remaining_with_no_ai),
    )
    return ranked_influencers
```

### New Method: _evaluate_preliminary()
```python
def _evaluate_preliminary(self, influencer: Influencer) -> EvaluatedInfluencer:
    """Evaluate influencer with preliminary (rule-based only) scoring.
    
    This is used in the first pass to quickly rank all influencers before
    expensive Gemini calls.
    """
    score_result = self.scoring_service.score_preliminary(influencer)
    fallback_analysis = AIAnalysis(
        detected_language=influencer.language or "unknown",
        niche="unknown",
        government_support_score=0,
        political_orientation="unknown",
        confidence=0.0,
        summary="",
        keywords=[],
        reasoning="",
    )
    return EvaluatedInfluencer(
        influencer=influencer,
        ai_analysis=fallback_analysis,
        score_result=score_result,
        rank=0,
        ai_analysis_performed=False,
    )
```

### New Method: _evaluate_with_ai()
```python
def _evaluate_with_ai(
    self,
    influencer: Influencer,
    ai_analysis: AIAnalysis | None,
    ai_analysis_performed: bool,
) -> EvaluatedInfluencer:
    """Evaluate influencer with full scoring (including AI if provided).
    
    Args:
        influencer: The influencer to evaluate.
        ai_analysis: The AI analysis result, or None/fallback if not performed.
        ai_analysis_performed: True if this influencer was actually analyzed by Gemini.
    """
    score_result = self.scoring_service.score(influencer, ai_analysis)
    return EvaluatedInfluencer(
        influencer=influencer,
        ai_analysis=ai_analysis or self._not_analyzed_fallback(influencer),
        score_result=score_result,
        rank=0,
        ai_analysis_performed=ai_analysis_performed,
    )
```

### New Method: _not_analyzed_fallback()
```python
@staticmethod
def _not_analyzed_fallback(influencer: Influencer) -> AIAnalysis:
    """Create fallback analysis for influencers not selected for AI analysis.
    
    This clearly indicates that the influencer was ranked below the threshold
    and was not sent to Gemini.
    """
    return AIAnalysis(
        detected_language=influencer.language or "unknown",
        niche="unknown",
        government_support_score=0,
        political_orientation="unknown",
        confidence=0.0,
        summary="Not analyzed (outside Top 10 by preliminary score)",
        keywords=[],
        reasoning="This influencer ranked outside the top threshold and was not analyzed by AI to reduce API costs.",
    )
```

---

## 6. ui/dashboard.py

### Updated Method: _render_details()
```python
def _render_details(evaluated_influencers: Sequence[EvaluatedInfluencer]) -> None:
    """Render expandable detail sections for each influencer."""
    st.subheader("View details")

    if not evaluated_influencers:
        return

    for result in evaluated_influencers:
        influencer = result.influencer
        ai_analysis = result.ai_analysis
        score_result = result.score_result
        
        # Build title with AI status indicator
        ai_status = "✓ AI Analyzed" if result.ai_analysis_performed else "⚠ Not AI Analyzed"
        title = f"#{result.rank} {influencer.name} (@{influencer.handle}) [{ai_status}]"
        
        with st.expander(title, expanded=False):
            st.markdown(f"**Bio:** {influencer.bio or 'No bio provided.'}")
            st.markdown("**Recent content:**")
            if influencer.recent_content:
                for item in influencer.recent_content:
                    st.write(f"- {item}")
            else:
                st.write("- No recent content provided.")

            # Show AI analysis section with appropriate status
            if result.ai_analysis_performed:
                st.markdown(f"**AI summary:** {ai_analysis.summary or 'No summary available.'}")
                st.markdown(f"**AI reasoning:** {ai_analysis.reasoning or 'No reasoning available.'}")
                st.markdown(f"**Keywords:** {', '.join(ai_analysis.keywords) if ai_analysis.keywords else 'None'}")
            else:
                st.warning(
                    "⚠️ **AI Analysis Not Performed**\n\n"
                    "This influencer ranked outside the top threshold and was not analyzed by Gemini AI to reduce API costs. "
                    "Only rule-based scoring was applied."
                )
                st.markdown(
                    f"*Reason: {ai_analysis.reasoning}*"
                )

            st.markdown("**Score breakdown:**")
            breakdown_df = pd.DataFrame(
                [
                    {"Criterion": criterion, "Contribution": contribution}
                    for criterion, contribution in score_result.score_breakdown.items()
                ]
            )
            st.dataframe(breakdown_df, hide_index=True, use_container_width=True)
            
            # Show preliminary vs final score info if not analyzed
            if not result.ai_analysis_performed:
                st.caption(
                    f"📊 Preliminary Score: {score_result.preliminary_score:.2f} | "
                    f"Final Score (rule-based): {score_result.total_score:.2f}"
                )
```

---

## Summary of Changes

| File | Change Type | Details |
|------|-------------|---------|
| config/scoring_config.py | Added | TOP_AI_ANALYSIS_COUNT constant |
| config/scoring_config.py | Modified | ScoringConfig dataclass with top_ai_analysis_count |
| models/score_result.py | Added | preliminary_score field |
| models/evaluated_influencer.py | Added | ai_analysis_performed flag |
| services/scoring_service.py | Added | score_preliminary() method |
| services/scoring_service.py | Added | _calculate_preliminary_score() method |
| services/scoring_service.py | Modified | score() now calculates preliminary_score |
| services/dashboard_service.py | Refactored | evaluate_influencers() with two-tier approach |
| services/dashboard_service.py | Added | _evaluate_preliminary() method |
| services/dashboard_service.py | Added | _evaluate_with_ai() method |
| services/dashboard_service.py | Added | _not_analyzed_fallback() method |
| ui/dashboard.py | Modified | _render_details() with AI status display |

---

## Key Formulas

### Preliminary Score (Rule-Based Only)
```
weights = language_weight + niche_weight + bio_weight + follower_weight + engagement_weight

preliminary_score = (
    (language_score × language_weight) +
    (niche_score × niche_weight) +
    (bio_score × bio_weight) +
    (follower_score × follower_weight) +
    (engagement_score × engagement_weight)
) / weights × 100
```

### Final Score (Rule-Based + AI)
```
weights = language_weight + niche_weight + bio_weight + follower_weight + engagement_weight + ai_weight

final_score = (
    (language_score × language_weight) +
    (niche_score × niche_weight) +
    (bio_score × bio_weight) +
    (follower_score × follower_weight) +
    (engagement_score × engagement_weight) +
    (ai_score × ai_weight)
) / weights × 100
```

Where:
- All scores are normalized to [0, 1]
- Weights are configured in config/scoring_config.py
- Only Top N influencers have ai_score > 0
- Remaining influencers have ai_score = 0

---

## Testing Code Examples

### Test Preliminary Scoring
```python
def test_preliminary_scoring():
    from services.scoring_service import ScoringService
    from config.scoring_config import ScoringConfig
    from models import Influencer
    
    service = ScoringService(ScoringConfig())
    influencer = Influencer(
        name="Test User",
        handle="testuser",
        platform="Instagram",
        followers=10000,
        language="English",
        bio="Creator and influencer"
    )
    
    result = service.score_preliminary(influencer)
    
    # Preliminary score should not include AI
    assert "ai_orientation" not in result.score_breakdown
    assert result.preliminary_score == result.total_score
    assert 0 <= result.preliminary_score <= 100

def test_top_n_selection():
    from services.dashboard_service import DashboardWorkflowService
    from config.scoring_config import ScoringConfig
    from models import Influencer
    
    config = ScoringConfig(top_ai_analysis_count=5)
    workflow = DashboardWorkflowService.create_default()
    
    # Create test influencers
    influencers = [
        Influencer(name=f"User{i}", handle=f"user{i}", platform="Instagram", followers=i*1000)
        for i in range(100)
    ]
    
    results = workflow.evaluate_influencers(influencers)
    
    # Check that only top 5 are analyzed
    analyzed = [r for r in results if r.ai_analysis_performed]
    assert len(analyzed) <= 5
    
    # Check that analyzed ones are in top ranks
    for result in analyzed:
        assert result.rank <= 5
```

---

## Migration Path

### For Existing Code
No changes required! The new system is backward compatible.

```python
# This code still works exactly the same
workflow = DashboardWorkflowService.create_default()
results = workflow.evaluate_influencers(influencers)
```

### To Use New Features
```python
# Check if AI was actually performed
for result in results:
    if result.ai_analysis_performed:
        print(f"Full AI analysis available for #{result.rank}")
    else:
        print(f"Rule-based scoring only for #{result.rank}")
```

---

## Verification

All files verified for:
- ✅ No syntax errors
- ✅ No import errors
- ✅ Type hints are correct
- ✅ All methods have docstrings
- ✅ Backward compatibility maintained
- ✅ No breaking changes to public APIs
