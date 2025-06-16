from sm_bluesky.common.plans import grid_fast_scan, grid_step_scan

from ..helper.add_meta import add_default_metadata

stxm_fast = add_default_metadata(grid_fast_scan)
stxm = add_default_metadata(grid_step_scan)


__all__ = ["stxm_fast", "stxm"]
