from __future__ import annotations

## formatter ##
import logging
import tempfile
import time
from pathlib import Path

from tests.utils import input_wigglesets, video_duration, video_frames
from wigglify.pipeline.concatenate_step import ConcatenateStep
from wigglify.pipeline.context import WiggleProcessorContext
from wigglify.pipeline.inputprepare_step import InputPrepareStep
from wigglify.pipeline.interpolate_step import InterpolateRifeStep
from wigglify.pipeline.pipeline import NextStep, Pipeline
from wigglify.pipeline.register_step import RegisterStep
from wigglify.pipeline.resize_step import ResizeStep

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)")

logger = logging.getLogger(__name__)


## glob all files and iterate as set:
def test_pipeline(tmp_path):
    wigglesets = input_wigglesets()

    print(f"Got {len(wigglesets)} wigglesets to process")

    for wiggleset in wigglesets:
        print(f"processing {wiggleset}")

        with tempfile.TemporaryDirectory(dir=tmp_path, prefix=wiggleset[0].name, delete=False) as tmpdirname:
            context = WiggleProcessorContext(wiggleset, temp_working_dir=Path(tmpdirname))
            steps = [
                InputPrepareStep(),
                ResizeStep((500, 500)),
                RegisterStep(apply_mask=True, crop_to_least_common_intersection=True, register_algorithm="featurebased"),
                InterpolateRifeStep(2),
                ConcatenateStep("video.gif", reverse_append=True),
            ]
            pipeline = Pipeline[WiggleProcessorContext](*steps)  # put it together

            def _error_handler(error: Exception, context: WiggleProcessorContext, next_step: NextStep) -> None:
                logger.exception(error)
                logger.error(f"Error applying step, error: {error}")
                raise error

            # run pipeline
            tms = time.time()
            pipeline(context, _error_handler)
            logger.debug(f"-- process time: {round((time.time() - tms), 2)}s to process pipeline")
            logger.debug(f"Resulting video: {context.processing_paths}")

            logger.info(video_duration(f"{context.temp_working_dir}/video.gif"))
            logger.info(video_frames(f"{context.temp_working_dir}/video.gif"))
