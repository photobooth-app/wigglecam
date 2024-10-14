from __future__ import annotations

import argparse
import re

## formatter ##
import time
import traceback
from pathlib import Path

from wigglify.pipeline.concatenate_step import ConcatenateStep
from wigglify.pipeline.context import WiggleProcessorContext
from wigglify.pipeline.inputprepare_step import InputPrepareStep
from wigglify.pipeline.interpolate_step import InterpolateRifeStep
from wigglify.pipeline.pipeline import NextStep, Pipeline
from wigglify.pipeline.register_step import RegisterStep
from wigglify.pipeline.resize_step import ResizeStep


def process(input_paths, output_path, resize, no_reverse, passes):
    context = WiggleProcessorContext(input_paths)
    steps = [InputPrepareStep()]
    if resize:
        print(f"resize before processing to {tuple(resize)}")
        steps.append(ResizeStep(tuple(resize)))
    steps.append(RegisterStep(apply_mask=True, crop_to_least_common_intersection=True, register_algorithm="featurebased"))
    steps.append(InterpolateRifeStep(passes))
    steps.append(ConcatenateStep(output_path, reverse_append=not no_reverse))
    pipeline = Pipeline[WiggleProcessorContext](*steps)

    def _error_handler(error: Exception, context: WiggleProcessorContext, next_step: NextStep) -> None:
        traceback.print_exception(error)
        print(f"Error applying step, error: {error}")
        raise error

    # run pipeline
    tms = time.time()
    pipeline(context, _error_handler)
    print(f"process time: {round((time.time() - tms), 2)}s to process pipeline")
    print(f"Resulting video: {context.processing_paths[0].absolute()}")


def process_interpolate(args):
    print("processing interpolate")
    print(args)

    input_paths = []
    for input_str in args.input:
        input_path = Path(input_str)
        if not input_path.exists():
            raise RuntimeError(f"file {input_str} does not exist")
        input_paths.append(input_path)

    output_path = Path(args.output)
    if output_path.exists():
        print(f"warning, output file {output_path} exists and will be overwritten")

    process(input_paths, output_path, args.resize, args.no_reverse, args.passes)


def process_batch(args):
    print("processing batch")
    print(args)
    wigglesets = input_wigglesets(args.input_match)
    # print(wigglesets)
    for wiggleset in wigglesets:
        print(f"processing wiggleset sequence {wiggleset[0]}")
        try:
            process(wiggleset, Path(f"{wiggleset[0].stem}.{args.output_type}"), args.resize, args.no_reverse, args.passes)
        except Exception as exc:
            print(f"Error processing wiggleset {wiggleset}, error {exc}")
            continue
        else:
            print("finished processing wiggle")


def input_wigglesets(user_input_pattern: str):
    wigglesets: list[list[Path]] = []

    input_dir = Path(user_input_pattern).parent
    base_filename = Path(user_input_pattern).name
    sequence_number_length = int(re.findall(r"%0([0-9]+)d", user_input_pattern)[0])
    # print(sequence_number_length)
    # print(user_input_pattern)
    # print(user_input_pattern % (0,))
    # print(input_dir)
    # print(base_filename)
    # print(base_filename % (0,))

    for fileset_file0 in Path(input_dir).glob(base_filename % (0,)):
        # print(fileset_file0)
        wiggleset = []

        for file in Path(input_dir).glob(f"{(str(fileset_file0.stem))[:-sequence_number_length]}*{fileset_file0.suffix}"):
            wiggleset.append(file)

        wigglesets.append(wiggleset)

    return wigglesets


def main():
    global_parser = argparse.ArgumentParser(
        prog="wigglify",
        description="Create wigglegrams from two images with frame interpolation.",
    )
    subparsers = global_parser.add_subparsers(title="subcommands", help="-")

    single_parser = subparsers.add_parser("interpolate", help="interpolate between two or more images")
    # single_parser.add_argument(**arg_template)
    single_parser.add_argument("input", nargs=2, type=str, help="two input images")
    single_parser.add_argument("output", help="output mp4/gif")
    single_parser.add_argument("-r", "--resize", nargs=2, type=int, help="resize keeping aspect ratio to WxH")
    single_parser.add_argument("-p", "--passes", type=int, help="how often to interpolate", default=2)
    single_parser.add_argument("--no_reverse", action="store_true", help="do not append reverse to output video")
    single_parser.set_defaults(func=process_interpolate)

    batch_parser = subparsers.add_parser("batch", help="batch interpolate sets of two or more images")
    # single_parser.add_argument(**arg_template)
    batch_parser.add_argument("input_match", type=str, help="input folder to find wigglesets as input", default="./tests/input_images/*_%02d.jpg")
    batch_parser.add_argument("output_type", choices=["mp4", "gif"], default="gif", help="output as mp4/gif")
    batch_parser.add_argument("-r", "--resize", nargs=2, type=int, help="resize keeping aspect ratio to WxH")
    batch_parser.add_argument("-p", "--passes", type=int, help="how often to interpolate", default=2)
    batch_parser.add_argument("--no_reverse", action="store_true", help="do not append reverse to output video")
    batch_parser.set_defaults(func=process_batch)

    args = global_parser.parse_args()
    print(args.func(args))


if __name__ == "__main__":
    main()
