from sm_bluesky.common.helper import add_default_metadata
from sm_bluesky.common.plans import grid_fast_scan, grid_step_scan

P99_DEFAULT_METADATA = {"energy": 1.8, "detector_dist": 88}

stxm_step = add_default_metadata(grid_step_scan, P99_DEFAULT_METADATA)
stxm_step.__name__ = "stxm_step"
stxm_fast = add_default_metadata(grid_fast_scan, P99_DEFAULT_METADATA)
stxm_fast.__name__ = "stxm_fast"

__all__ = ["stxm_fast", "stxm_step", "new_count"]
