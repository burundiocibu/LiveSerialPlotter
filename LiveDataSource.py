# -*- coding: utf-8 -*-
"""
This class takes care of getting up-to-date data. It spawns off a thread to keep
some np arrays up-to-date and also provides some tk callbacks to configure it.

It accepts data from either a serial port or from a udp socket.
"""
import logging
import datetime
import queue
import serial
import serial.tools.list_ports
import socket
import threading
import time

logger = logging.getLogger(__name__)

TIMEOUT = 0.25  # Seconds to wait in the serial loop
BUFFSIZE = 1492  # buffersize for UDP socket


class LiveDataSource:
    """Class to provide a real-time stream of data to a consumer.

    Data and times of data receiption are provided to the consumer in queues

    Attributes:
        data: a queue with a date time object and a list for each set of observations received
        labels: a list of labels for each item in the list of observations
    """

    def __init__(self, source: str = "test:100", log_rx=False):
        """Constructor for LiveDataSource

        Args:
            source: Indicates what serial port, udp port, or test source to use a source of data.
                examples:
                 "serial:/cu/usbmodem..."
                 "udp:<address>:<port>"
                 "test:<rate>"
            log_rx: Log received packets
        """
        super().__init__()
        self.time_to_die = False
        self.require_brackets = False
        self.io_thread = None
        self.tx_thread = None
        self.log_rx = log_rx

        self.data = queue.SimpleQueue()
        self.labels = []

        daemon_me = False
        if source.startswith("serial:"):
            port = source.removeprefix("serial:")
            self.io_thread = threading.Thread(target=self.serial_rx, args=(port, 115200))
            self.io_thread.setDaemon(daemon_me)
            self.io_thread.start()
            logger.debug(f"thread {self.io_thread.name} started")
        elif source.startswith("udp:"):
            port = int(source.removeprefix("udp:"))
            addr = "192.168.86.102"
            self.io_thread = threading.Thread(target=self.udp_rx, args=(addr, port))
            self.io_thread.setDaemon(daemon_me)
            self.io_thread.start()
        elif source.startswith("test:"):
            rate = float(source.removeprefix("test:"))
            addr = "127.0.0.1"
            port = 10000
            self.io_thread = threading.Thread(target=self.udp_rx, args=(addr, port))
            self.io_thread.setDaemon(daemon_me)
            self.io_thread.start()
            logger.debug(f"thread {self.io_thread.name} started")
            self.tx_thread = threading.Thread(target=self.udp_tx, args=(rate, addr, port))
            self.tx_thread.setDaemon(daemon_me)
            self.tx_thread.start()
            logger.debug(f"thread {self.tx_thread.name} started")

        logger.info("Waiting for label names...")
        while len(self.labels) < 2:
            time.sleep(0.05)
        logger.info(f"Got them: {self.labels}")

    def stop(self):
        """Stop io thread and tx thread if it is running"""
        logger.info("stopping io_thread...")
        self.time_to_die = True
        logger.debug(f"data.qsize:{self.data.qsize()}")
        self.io_thread.join()
        logger.info("stopped io_thread...")
        if self.tx_thread is not None:
            self.tx_thread.join()
            logger.info("stopped tx_thread...")

    def parse_data(self, rawdata):
        """Parse  values and optionally labels out of rawdata and put them on the queue."""
        values = [time.time()]
        values = [datetime.datetime.now()]
        new_labels = ["time"]
        rawdata = rawdata.decode("utf8").strip()
        if len(rawdata) == 0:
            return

        if self.log_rx:
            logger.debug(f"rx:{rawdata}")

        l = rawdata.rfind(">")
        if l == -1:
            logger.warning(f"no > delimiter: {rawdata}")
            return
        if self.require_brackets:
            r = rawdata.find("<")
            if r == -1:
                logger.warning("no < delimiter")
                return
        else:
            r = len(rawdata[l + 1 :])
        try:
            i = 0
            for s in rawdata[l + 1 : r].split(" "):
                l = s.rfind(":")
                if l > 0:
                    values.append(float(s[l + 1 :]))
                    new_labels.append(s[:l])
                else:
                    values.append(float(s))
                    new_labels.append(str(i))
                i += 1
            if new_labels != self.labels:
                self.labels = new_labels
            self.data.put(values)
        except ValueError:
            logger.warning(f"failed to convert {rawdata}")

    def serial_rx(self, port, baudrate):
        ser = serial.Serial(port, baudrate, timeout=TIMEOUT)
        ser.flushInput()
        logger.info(f"connected to {port} at {baudrate}, log_rx:{self.log_rx}")
        while not self.time_to_die:
            self.parse_data(ser.readline())
        ser.close()
        logger.info("serial_rx done")

    def udp_rx(self, addr, port):
        sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        sock.bind((addr, port))
        sock.settimeout(0.2)
        logger.info(f"listening on {addr}:{port}, log_rx:{self.log_rx}")
        while not self.time_to_die:
            try:
                rawdata, _ = sock.recvfrom(BUFFSIZE)
                self.parse_data(rawdata)
            except TimeoutError:
                pass
        logger.info("udp_rx done")

    def t(self):
        return time.clock_gettime(time.CLOCK_MONOTONIC)

    def udp_tx(self, tx_rate, addr, port):
        """A dummy datasource for testing."""
        sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

        i = 0
        delay = 1.0 / tx_rate
        logger.info(f"sending test data to {addr}:{port} at {tx_rate} Hz ({1e3*delay:.0f}ms)")
        if delay <= 0.1:
            imax = int(1 / delay)
        elif delay <= 1:
            imax = int(10 / delay)
        else:
            imax = int(60 / delay)
        st = delay
        t = self.t() - delay
        while not self.time_to_die:
            err = t - self.t() + st
            p = 100 * i / imax
            e = delay - st
            msg = f">i:{p:.3f} dt(ms):{1e3*(e):.3}<"
            sock.sendto(str.encode(msg), (addr, port))
            i += 1
            if i >= imax:
                i = 0
            st = max(0.005, delay + err)
            t = self.t()
            time.sleep(st - 0.005)

        logger.info("udp_tx done")

    def get_data(self):
        """This function will be running on a seperate thread from the data sources."""
        while not self.time_to_die:
            new_data = []
            while self.data.qsize() > 0:
                new_data.append(self.data.get(False))
            yield new_data
