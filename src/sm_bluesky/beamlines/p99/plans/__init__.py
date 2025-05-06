from sm_bluesky.common.plans import stxm_fast, stxm_step

from ..helper.add_meta import add_default_metadata

stxm_fast = add_default_metadata(stxm_fast)
stxm_step = add_default_metadata(stxm_step)


all = ["stxm_fast", "stxm_step"]
