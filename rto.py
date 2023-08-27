#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import queue
import serial.tools.list_ports
import sys
import time

from LiveDataSource import LiveDataSource
from OScope import OScope
logger = logging.getLogger(__name__)


def setup():
    parser = argparse.ArgumentParser(description="cli test for LiveDataSource")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity of outut"
    )
    parser.add_argument(
        "-w",
        "--window-size",
        default=10,
        help="Initial width of plot, in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "-s",
        "--source",
        default="test:100",  # a 100 Hz data source
        help="Where to take data from. ",
    )

    parser.add_argument(
        "-l",
        "--list-serial-ports",
        default=False,
        action="store_true",
        help="List serial ports and exit",
    )

    args = parser.parse_args()

    if args.verbose == 0:
        level = logging.WARNING
    elif args.verbose == 1:
        level = logging.INFO
    elif args.verbose > 1:
        level = logging.DEBUG

    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d: [%(threadName)s] %(message)s",
        level=level,
        stream=sys.stdout,
        datefmt="%H:%M:%S",
    )

    if args.list_serial_ports:
        for p, d, h in serial.tools.list_ports.comports():
            print(f"{p}, {d}, {h}")
        sys.exit(0)

    return args


try:
    args = setup()
    data = []
    lds = LiveDataSource(args.source, args.verbose>2)
    scope = OScope(args)

    while not scope.time_to_die:
        new_data = 0
        try:
            logger.debug(f"qsize:{lds.data.qsize()}")
            while True:
                data.append(lds.data.get(False))
                new_data += 1
        except queue.Empty:
            pass
        if new_data == 0:
            time.sleep(0.05)
            continue
        scope.set_labels(lds.labels)
        scope.makeFig(data)
        # keep list from growing chewing up memory
        if scope.imin > 200:
            data = data[scope.imin :]
            logger.info(f"imin:{scope.imin}")
except KeyboardInterrupt:
    pass
lds.stop_rx()
