from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any
import pandas as pd

class DataProvenance(Enum):
    REAL_QUESTDB      = "real_questdb"
    REAL_PARQUET      = "real_parquet"
    REAL_ALPACA       = "real_alpaca"
    SYNTHETIC_GBM     = "synthetic_gbm"
    SYNTHETIC_REGIME  = "synthetic_regime"
    SYNTHETIC_DECAY   = "synthetic_decay"

    @property
    def is_synthetic(self) -> bool:
        return self.value.startswith("synthetic")

class SyntheticDataError(RuntimeError):
    """Raised when synthetic data is used in a strict/validation run."""

@dataclass
class SourcedData:
    data: Any                   # pd.DataFrame or np.ndarray for decay stream
    provenance: DataProvenance
    rows: int
    symbol: Optional[str] = None

def enforce_provenance(prov: DataProvenance, *, allow_synthetic: bool) -> None:
    if prov.is_synthetic and not allow_synthetic:
        raise SyntheticDataError(
            f"Refusing to run: data source is '{prov.value}'. "
            f"This is a validation run and synthetic data is not permitted. "
            f"Pass --allow-synthetic (or ALLOW_SYNTHETIC=1) to run against synthetic data explicitly."
        )
