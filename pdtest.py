#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import datetime
from LiveDataSource import LiveDataSource
import logging
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import queue
import serial.tools.list_ports
import sys
import time

logger = logging.getLogger(__name__)


class OScope:
    def __init__(self, args):
        self.x_width = datetime.timedelta(seconds=args.window_size)

    def makeFig(self, t, d, labels):
        plt.clf()
        plt.grid(True, which="both")
        plt.ylabel("data")
        gca = plt.gca()
        gca.set_xlim(t[0], t[0] + self.x_width)
        #gca.set_ylim(-50, 50)
        gca.tick_params(which="minor", width=0.75, length=2.5)
        gca.xaxis.set_ticks_position("bottom")
        gca.xaxis.set_major_formatter(mdates.DateFormatter("%M:%S"))
        gca.xaxis.set_minor_locator(ticker.MultipleLocator(0.2))
        gca.yaxis.set_minor_locator(ticker.MultipleLocator(5))
        for i in range(len(labels)):
            plt.plot(t, d[i], "-", label=labels[i])
        plt.legend(loc="lower right")

def setup():

    parser = argparse.ArgumentParser(description="cli test for LiveDataSource")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity of outut"
    )
    parser.add_argument(
        "-w",
        "--window-size",
        default=10,
        help="Initial width of plot, in seconds (default: %(default)s)"
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

    plt.set_loglevel(level="warning")
    return args


try:
    args = setup()
    data = []
    times = []
    labels = []
    lds = LiveDataSource(args.source)
    scope = OScope(args)
    plt.ion()
    while True:
        new_data = 0
        try:
            logger.debug(f"qsize:{lds.data.qsize()}")
            while True:
                t, d = lds.data.get(False)
                times.append(t)
                data.append(d + [1e3*(datetime.datetime.now()-t).total_seconds()])
                new_data += 1
        except queue.Empty:
            pass
        if new_data==0:
            logger.debug("pausing")
            plt.pause(0.000001)
            time.sleep(0.02)
            continue
        if len(times) == 0:
            continue
        t = np.array(times)
        d = np.array(data).T
        scope.makeFig(t, d, lds.labels+["dtw(ms)"])
        excess = len(times) - 500
        if excess > 0:
            data = data[excess:]
            times = times[excess:]
except KeyboardInterrupt:
    pass
lds.stop_rx()