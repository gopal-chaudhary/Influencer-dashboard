# Developer Quick Reference: Top 10 AI Analysis

## Modified Files Summary

### 1. Configuration (`config/scoring_config.py`)
**Changes:**
- Added `TOP_AI_ANALYSIS_COUNT = 10` constant
- Added `top_ai_analysis_count: int` field to `ScoringConfig` dataclass
- Added validation in `__post_init__()` for the new field

**Use:**
```python
config = ScoringConfig()
print(config.top_ai_analysis_count)  # 10

# Customize:
config = ScoringConfig(top_ai_analysis_count=25)
```

---

### 2. Scoring Service (`services/scoring_service.py`)
**New Method:** `score_preliminary(influencer) -> ScoreResult`
- Scores using only rule-based criteria (no AI)
- Returns `ScoreResult` with `preliminary_score` set
- Used for initial ranking of all influencers

**Updated Method:** `score(influencer, ai_analysis) -> ScoreResult`
- Now calculates both `preliminary_score` and `total_score`
- Includes AI orientation in final score

**Changes to ScoreResult:**
- Added `preliminary_score` field to track rule-based score
- `total_score` includes AI component

---

### 3. Dashboard Service (`services/dashboard_service.py`)
**New Workflow:** `evaluate_influencers(influencers) -> list[EvaluatedInfluencer]`
- Step 1: Score all with `score_preliminary()`
- Step 2: Sort and select Top N
- Step 3-4: Analyze Top N with Gemini
- Step 5: Keep rest with preliminary scores
- Step 6: Merge and rank all

**New Methods:**
- `_evaluate_preliminary(influencer)` - First pass scoring
- `_evaluate_with_ai(influencer, ai_analysis, ai_analysis_performed)` - Full scoring with AI flag
- `_not_analyzed_fallback(influencer)` - Creates fallback analysis for non-analyzed influencers

**Key Variables:**
- `top_n = config.top_ai_analysis_count` - Number for AI analysis
- `sorted_by_preliminary` - All influencers sorted by preliminary score
- `ai_analysis_performed` - Flag tracking if AI was actually used

---

### 4. Models

#### `models/evaluated_influencer.py`
```python
@dataclass
class EvaluatedInfluencer:
    influencer: Influencer
    ai_analysis: AIAnalysis
    score_result: ScoreResult
    rank: int = 0
    ai_analysis_performed: bool = False  # NEW
```

#### `models/score_result.py`
```python
@dataclass
class ScoreResult:
    total_score: float
    preliminary_score: float = 0.0  # NEW
    score_breakdown: dict[str, float]
    matched_languages: list[str]
    matched_niches: list[str]
    remarks: list[str]
```

---

### 5. Dashboard UI (`ui/dashboard.py`)
**Updated:** `_render_details(evaluated_influencers)`
- Shows "✓ AI Analyzed" or "⚠ Not AI Analyzed" in expander title
- For analyzed: Shows AI summary, reasoning, keywords
- For not analyzed: Shows warning message explaining why
- Shows preliminary vs final score for non-analyzed

---

## Usage Examples

### Basic Usage
```python
from services.dashboard_service import DashboardWorkflowService
from models import Influencer

# Create service (uses default config with TOP_AI_ANALYSIS_COUNT=10)
workflow = DashboardWorkflowService.create_default()

# Evaluate influencers
influencers = [...]  # 1000+ influencers
results = workflow.evaluate_influencers(influencers)

# Check which were analyzed
for result in results:
    if result.ai_analysis_performed:
        print(f"Rank {result.rank}: {result.influencer.name} - AI Analyzed")
    else:
        print(f"Rank {result.rank}: {result.influencer.name} - Not Analyzed")
```

### Custom Configuration
```python
from config.scoring_config import ScoringConfig
from services.dashboard_service import DashboardWorkflowService
from services.scoring_service import ScoringService
from services.grok_service import GrokService

# Configure to analyze only Top 5
config = ScoringConfig(top_ai_analysis_count=5)
scoring_service = ScoringService(config)
grok_service = GrokService()

workflow = DashboardWorkflowService(
    grok_service=grok_service,
    scoring_service=scoring_service
)

results = workflow.evaluate_influencers(influencers)
# Now only Top 5 will have AI analysis
```

### Scoring Individually
```python
from services.scoring_service import ScoringService
from config.scoring_config import ScoringConfig

service = ScoringService(ScoringConfig())

# Preliminary (rule-based only) - Used for initial ranking
preliminary = service.score_preliminary(influencer)
print(preliminary.preliminary_score)  # 75.0
print(preliminary.total_score)        # 75.0 (same, no AI)

# Full (with AI) - Used for Top N after Gemini analysis
full = service.score(influencer, ai_analysis)
print(full.preliminary_score)  # 75.0 (rule-based component)
print(full.total_score)        # 82.5 (includes AI orientation)
```

### Filtering by Analysis Status
```python
# Get only analyzed influencers
analyzed = [r for r in results if r.ai_analysis_performed]

# Get only non-analyzed influencers
not_analyzed = [r for r in results if not r.ai_analysis_performed]

# Statistics
print(f"Analyzed: {len(analyzed)} | Not analyzed: {len(not_analyzed)}")
```

---

## Key Concepts

### Preliminary Score
- **What:** Rule-based score computed for ALL influencers
- **When:** First pass, before Gemini calls
- **Uses:** Follower, language, niche, bio, engagement
- **Excludes:** AI orientation
- **Purpose:** Quick ranking to identify Top N candidates

### Final Score
- **What:** Weighted score combining rule-based + AI
- **When:** After Gemini analysis (only for Top N)
- **Uses:** Follower, language, niche, bio, engagement, AI orientation
- **Purpose:** Accurate ranking with AI insights

### AI Analysis Flag
- **What:** `ai_analysis_performed` boolean on `EvaluatedInfluencer`
- **True:** This influencer was sent to Gemini (in Top N)
- **False:** This influencer was ranked below threshold (not sent to Gemini)
- **UI Use:** Show/hide detailed AI analysis sections

---

## API Changes (Breaking vs Non-Breaking)

### Non-Breaking (Backward Compatible)
- Existing code continues to work
- `ScoringService.score()` still accepts same parameters
- `DashboardWorkflowService.evaluate_influencers()` still returns same type

### Behavioral Changes (Important!)
- All influencers are now scored in two passes
- Only Top N get Gemini analysis
- Output includes `ai_analysis_performed` flag (new field)
- Performance changed (faster for large datasets)

### If Upgrading
1. **No code changes required** - existing code works as-is
2. **Check dashboard UI** - uses new `ai_analysis_performed` flag
3. **Update tests** - if you were checking `ai_analysis.summary` for all influencers
4. **Adjust thresholds** - if `TOP_AI_ANALYSIS_COUNT` needs customization

---

## Testing

### Unit Testing
```python
import pytest
from services.scoring_service import ScoringService
from config.scoring_config import ScoringConfig
from models import Influencer

def test_preliminary_score():
    service = ScoringService(ScoringConfig())
    inf = Influencer(name="Test", handle="test", platform="Instagram", followers=10000)
    
    result = service.score_preliminary(inf)
    
    # Preliminary score should not include AI
    assert 0 <= result.preliminary_score <= 100
    assert "AI orientation" not in result.score_breakdown
    assert result.preliminary_score == result.total_score

def test_top_n_selection():
    from services.dashboard_service import DashboardWorkflowService
    
    config = ScoringConfig(top_ai_analysis_count=10)
    workflow = DashboardWorkflowService.create_default()
    
    # Create 100 test influencers
    influencers = [
        Influencer(name=f"User{i}", handle=f"user{i}", platform="Instagram", followers=i*1000)
        for i in range(100)
    ]
    
    results = workflow.evaluate_influencers(influencers)
    
    # Check that only top 10 are analyzed
    analyzed = [r for r in results if r.ai_analysis_performed]
    assert len(analyzed) <= 10
    
    # Check that analyzed ones are top ranked
    for i in range(min(10, len(results))):
        assert results[i].rank <= 10
```

### Integration Testing
```python
def test_full_workflow():
    workflow = DashboardWorkflowService.create_default()
    
    influencers = load_test_dataset("test_data.csv")  # 1000+ influencers
    results = workflow.evaluate_influencers(influencers)
    
    # Verify all influencers are returned
    assert len(results) == len(influencers)
    
    # Verify only top 10 have AI analysis
    analyzed = [r for r in results if r.ai_analysis_performed]
    assert len(analyzed) <= 10
    
    # Verify scores are reasonable
    for result in results:
        assert 0 <= result.score_result.total_score <= 100
        assert 0 <= result.score_result.preliminary_score <= 100
    
    # Verify ranking is sorted by total score
    for i in range(len(results) - 1):
        assert results[i].score_result.total_score >= results[i+1].score_result.total_score
```

---

## Troubleshooting

### Issue: All influencers show "Not analyzed"
**Cause:** `TOP_AI_ANALYSIS_COUNT = 0`
**Fix:** Set to positive integer in `config/scoring_config.py`

### Issue: API usage is unchanged
**Cause:** `TOP_AI_ANALYSIS_COUNT` is set to `len(influencers)` or very high
**Fix:** Reduce `TOP_AI_ANALYSIS_COUNT` to desired threshold (e.g., 10)

### Issue: Dashboard shows wrong AI status
**Cause:** UI not checking `ai_analysis_performed` flag
**Fix:** Verify UI code calls `if result.ai_analysis_performed`

### Issue: Preliminary and final scores are the same for Top 10
**Cause:** AI analysis returned 0 confidence or failed silently
**Fix:** Check logs for Gemini errors, verify API key is set

---

## Performance Notes

### Time Complexity
- Preliminary scoring: O(n log n) where n = number of influencers
- Gemini calls: O(1) - constant regardless of dataset size (only Top N)
- Ranking: O(n log n)
- **Total:** O(n log n) dominated by sorting, not API calls

### Space Complexity
- Stores all influencers in memory: O(n)
- AI analysis map: O(top_ai_analysis_count) = O(1) in practice
- **Total:** O(n) - linear

### Optimization Opportunities
1. **Batch preliminary scoring** in chunks if memory is tight
2. **Cache preliminary scores** between runs
3. **Incremental updates** - re-score only new influencers
4. **Parallel processing** - score preliminary in parallel threads

---

## Version History

### v1.0 (Current)
- Two-tier evaluation approach
- Configurable `TOP_AI_ANALYSIS_COUNT`
- `ai_analysis_performed` flag on results
- Backward compatible with existing code

### Future Versions
- v1.1: Confidence-based filtering
- v1.2: Dynamic threshold adjustment
- v1.3: Caching and incremental updates
- v2.0: Parallel processing support
