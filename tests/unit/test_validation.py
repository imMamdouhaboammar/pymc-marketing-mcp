import pandas as pd
from marketing_mcp.domain.datasets.validation import validate_mmm_dataset

def test_validation_flags_duplicate_periods_and_negative_spend():
    df = pd.DataFrame({
      "date": ["2026-01-05","2026-01-05","2026-01-19"],
      "revenue": [10,12,13],
      "meta": [1,-2,3],
    })
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [])
    codes={f.code for f in findings}
    assert "DUPLICATE_PERIOD" in codes
    assert "NEGATIVE_MEDIA" in codes

def test_validation_detects_high_channel_correlation():
    n=60
    df=pd.DataFrame({"date":pd.date_range("2025-01-06",periods=n,freq="W-MON"), "revenue":range(n), "meta":range(n), "tiktok":[x*2 for x in range(n)]})
    findings=validate_mmm_dataset(df,"date","revenue",["meta","tiktok"],[])
    assert any(f.code=="HIGH_CHANNEL_CORRELATION" for f in findings)
