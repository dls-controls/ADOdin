import argparse
import ctypes
import logging
from datetime import datetime
from os import makedirs
from pathlib import Path
from time import sleep

from cothread import Event
from cothread.catools import DBR_CHAR_STR, ca_nothing, caget, camonitor, caput
from timeout_decorator import TimeoutError, timeout

WAIT_PV_TIMEOUT_SECONDS = 30
ACQ_TIME_DELTA = 1e-7


class EigerUnreachableError(Exception):
    pass


class FPError(Exception):
    pass


class EigerTestDetector:
    def __init__(self, pv_stem: str, file_writing_enabled: bool, fp_count: int):
        self.pv_stem = pv_stem
        self.file_writing_enabled = file_writing_enabled
        self.fp_count = fp_count

        # We will increment this value each time we complete an acq
        self.acquisition_id = 1

        # List of attempted acquisitions
        self.acquisition_log = []

        try:
            logging.debug("Checking detector online")
            self.get("CAM:PortName_RBV")
        except ca_nothing:
            logging.error("Detector Unreachable")
            raise EigerUnreachableError

    def wait_on_pv_to_val(
        self,
        param,
        desired_value,
        timeout_seconds=WAIT_PV_TIMEOUT_SECONDS,
        datatype=None,
    ):
        @timeout(timeout_seconds)
        def timeout_wait_on_pv_to_val(param, desired_value):
            current_value = caget(f"{self.pv_stem}:{param}", datatype=datatype)
            if current_value != desired_value:
                done = Event()

                def check_equals_desired(value):
                    if value == desired_value:
                        done.Signal()

                logging.debug(
                    f"Waiting for {self.pv_stem}:{param} to be {desired_value}"
                )
                m = camonitor(
                    f"{self.pv_stem}:{param}", check_equals_desired, datatype=datatype
                )
                done.Wait()
                m.close()
                logging.debug(f"{self.pv_stem}:{param} now equal to {desired_value}")
            else:
                logging.debug(
                    f"Checked {self.pv_stem}:{param} once and it was already equal "
                    + f"to {desired_value}"
                )

        return timeout_wait_on_pv_to_val(param, desired_value)

    def put(self, param, val, datatype=None, wait=True):
        caput(f"{self.pv_stem}:{param}", val, datatype=datatype, wait=wait, timeout=10)
        logging.debug(f"Put {param} to {val}")

    def get(self, param, datatype=None):
        logging.debug(f"Called caget {param}")
        return caget(f"{self.pv_stem}:{param}", datatype=datatype, timeout=10)

    def put_eiger_params(self, acquire_period, num_images):
        self.put("CAM:ManualTrigger", "Yes")
        self.put("CAM:AcquireTime", acquire_period - ACQ_TIME_DELTA)
        self.put("CAM:AcquirePeriod", acquire_period)
        self.put("CAM:ImageMode", "Multiple")
        self.put("CAM:NumImages", num_images)
        self.put("CAM:TriggerMode", "Internal Series")
        self.put("CAM:NumTriggers", 1)
        self.put("CAM:StreamEnable", "Yes")

    def put_odin_params(self, file_name, file_path):
        self.put("OD:FileName", str(file_name), datatype=DBR_CHAR_STR)
        # Make sure FileName propagates through database logic
        self.wait_on_pv_to_val("OD:META:FileName_RBV", file_name, datatype=DBR_CHAR_STR)
        self.wait_on_pv_to_val("OD:AcquisitionID_RBV", file_name, datatype=DBR_CHAR_STR)

        self.put("OD:FilePath", str(file_path), datatype=DBR_CHAR_STR)

        # Get number of frames to wait for
        num_capture = self.get("CAM:NumImages")
        self.put("OD:NumCapture", num_capture)

        # Wait for confirmation there are no stale parameters
        self.wait_on_pv_to_val("CAM:StaleParameters_RBV", 0)

        # Get the data type
        eiger_bit_depth = self.get("CAM:BitDepthImage_RBV")
        self.put("OD:DataType", "UInt" + str(eiger_bit_depth))  # 8, 16 or 32
        self.put("OD:Capture", 1, wait=False)

        # Wait for data file writing and meta file writing to be ready
        self.wait_on_pv_to_val("OD:Capture_RBV", 1)
        self.wait_on_pv_to_val("OD:META:Writing_RBV", 1)

    def acquire_manual_trigger(self, wait_time):
        self.put("CAM:Acquire", 1, wait=False)

        # Wait on fan ready (this waits on detector armed itself)
        if self.file_writing_enabled:
            self.wait_on_pv_to_val("OD:FAN:StateReady_RBV", 1)
        self.put("CAM:Trigger", 1)

        # Block until all images are received then return to allow disarm
        if self.file_writing_enabled:
            self.wait_on_pv_to_val("OD:Capture_RBV", 0, wait_time)
        else:
            sleep(10)
            print("Finished sleep - file writing should be complete")

    def disarm(self):
        if self.file_writing_enabled:
            self.put("OD:StartTimeout", 1, wait=False)
        self.put("CAM:Acquire", 0)

    def clear_previous_acquisition_failures(self):
        self.disarm()
        if self.file_writing_enabled:
            self.put("OD:Capture", 0)
            self.clear_fp_errors()

    def clear_fp_errors(self):
        for fp in range(1, self.fp_count + 1):
            self.put(f"OD{fp}:FPClearErrors", 1)

    def get_fp_errors(self):
        # Check for file writer errors
        fp_errors = [
            "".join(
                str(
                    ctypes.string_at(self.get(f"OD{fp}:FPErrorMessage_RBV").ctypes.data)
                )
            )
            for fp in range(1, self.fp_count + 1)
        ]
        return fp_errors

    def get_num_fp_errors(self):
        fp_states = [
            self.get(f"OD{fp}:FPErrorState_RBV") for fp in range(1, self.fp_count + 1)
        ]
        return sum(fp_states)

    def prepare_and_run_acquisition(
        self, filename, filepath, acquire_period=0.05, num_images=1
    ):
        now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        success = False

        logging.info(f"Attempting acq with ID {self.acquisition_id}")
        try:
            self.clear_previous_acquisition_failures()
            self.put_eiger_params(acquire_period, num_images)
            if self.file_writing_enabled:
                self.put_odin_params(filename, filepath)
            self.acquire_manual_trigger(
                WAIT_PV_TIMEOUT_SECONDS + acquire_period * num_images
            )
            self.disarm()
            if self.file_writing_enabled:
                if self.get_num_fp_errors():
                    # If we have fp errors, set success to False and raise an error
                    success = False
                    raise FPError("One or more FP in error state")
            else:
                success = True
        except TimeoutError:
            logging.error("Acquisition failed due to wait for PV timeout")
            raise
        except Exception:
            logging.error(
                "Acquisition failed due to error other than wait for PV timeout"
            )
            raise
        finally:
            acquisition_parameters = {
                "ID": self.acquisition_id,
                "time": now,
                "success": success,
                "fp_errors": self.get_fp_errors()
                if self.file_writing_enabled
                else "NA",
                "filename": filename,
                "filepath": filepath,
                "acquire_period": acquire_period,
                "num_images": num_images,
            }
            self.acquisition_log.append(acquisition_parameters)
            self.acquisition_id += 1
            logging.info(f"Acq parameters: {acquisition_parameters}")


def parse_args():
    def parameter_pair(arg):
        test = arg.split(",")
        return float(test[0]), int(test[1])

    parser = argparse.ArgumentParser(
        description="Run one or more test odin-eiger acquisitions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "pv_stem", type=str, help="The Eiger PV stem e.g. BL04I-EA-EIGER-01"
    )
    parser.add_argument(
        "parameter_list",
        type=parameter_pair,
        nargs="+",
        help="Comma separated pairs of acquisition period and number of images. "
        + "Separate pairs with whitespace e.g. 0.005,100 0.02,10",
    )
    parser.add_argument("filepath", type=Path, help="Path to data directory")
    parser.add_argument(
        "filename",
        type=str,
        help="Data filename stem (will be appended with acquisition num if multiple "
        + "acquisitions)",
    )
    parser.add_argument(
        "--log-directory",
        default=None,
        type=Path,
        help="Directory to write log file",
    )
    parser.add_argument(
        "--log-name",
        default="eiger_test.log",
        type=str,
        help="Filename of log file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="DEBUG",
        type=str,
        help="Log level",
    )
    parser.add_argument(
        "--runs",
        default=1,
        type=int,
        help="How many times to run the acquisition(s)",
    )
    parser.add_argument(
        "--delay",
        default=0,
        type=int,
        help="Delay (in seconds) between acquisitions",
    )
    parser.add_argument(
        "--directory-blocks",
        default=0,
        type=int,
        help="Number of acquisitions per directory - default don't create directories",
    )
    parser.add_argument(
        "--no-file-writing",
        action="store_true",
        default=False,
        help="Do not configure file writing and use sleeps instead",
    )
    parser.add_argument(
        "--fp-count", default=4, type=int, help="Number of frame processors"
    )

    args = parser.parse_args()

    if args.log_directory is None:
        args.log_directory = args.filepath

    return args


def main():
    args = parse_args()

    logging.basicConfig(
        filename=args.log_directory / args.log_name,
        level=args.log_level,
        format="%(asctime)s.%(msecs)03d:%(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    detector = EigerTestDetector(args.pv_stem, not args.no_file_writing, args.fp_count)

    file_path = args.filepath
    run = 0
    while True:
        logging.info(f"Run {run}")

        if args.directory_blocks and run % args.directory_blocks == 0:
            file_path = args.filepath / f"{run // args.directory_blocks}"
            makedirs(file_path, exist_ok=True)

        # Note odin requires different file names for sequential acquisitions
        for id, (acquire_period, num_images) in enumerate(args.parameter_list):
            filename = f"{args.filename}_{run}_{id}"
            detector.prepare_and_run_acquisition(
                filename, file_path, acquire_period, num_images
            )
            if args.delay:
                logging.debug(f"Acquisition complete - Waiting {args.delay} seconds")
                sleep(args.delay)

        run += 1
        if args.runs > 0 and run >= args.runs:
            logging.info(f"All {args.runs} runs complete")
            break


if __name__ == "__main__":
    main()
