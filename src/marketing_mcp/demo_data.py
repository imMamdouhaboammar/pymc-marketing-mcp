from __future__ import annotations
import numpy as np
import pandas as pd

def _adstock(x,alpha):
    out=np.zeros_like(x,dtype=float)
    for i,v in enumerate(x): out[i]=v+(alpha*out[i-1] if i else 0)
    return out
def _sat(x,k): return x/(x+k)
def generate_synthetic_mmm(n=156,seed=42):
    rng=np.random.default_rng(seed); dates=pd.date_range("2023-01-02",periods=n,freq="W-MON"); t=np.arange(n); discount=(rng.random(n)<.15).astype(float); meta=rng.gamma(5,20000,n); google=rng.gamma(6,18000,n); tiktok=rng.gamma(3,13000,n); youtube=rng.gamma(4,15000,n); season=250_000*np.sin(2*np.pi*t/52); media=1_100_000*_sat(_adstock(meta,.55),160_000)+1_400_000*_sat(_adstock(google,.25),130_000)+650_000*_sat(_adstock(tiktok,.35),110_000)+800_000*_sat(_adstock(youtube,.60),170_000); revenue=2_000_000+season+400_000*discount+media+rng.normal(0,120_000,n); return pd.DataFrame({"date":dates,"meta":meta,"google":google,"tiktok":tiktok,"youtube":youtube,"discount":discount,"revenue":np.maximum(revenue,1)})
