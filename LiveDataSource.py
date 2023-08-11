# -*- coding: utf-8 -*-
"""
This class takes care of getting up-to-date data. It spawns off a thread to keep
some np arrays up-to-date and also provides some tk callbacks to configure it.

It accepts data from either a serial port or from a udp socket.
"""
from argparse import Namespace
import datetime
import logging
import queue
import random
import serial
import serial.tools.list_ports
import sys
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

    def __init__(self, source: str):
        """Constructor for LiveDataSource

        Args:
            source: Indicates what serial port, udp port, or test source to use a source of data.
                examples:
                 "serial:/cu/usbmodem..."
                 "udp:/<address>:<port>"
                 "test:<rate>"
        """
        super().__init__()
        self.ser = None
        self.udp_sender = False
        self.udp_socket = None
        self.time_to_die = False
        self.require_brackets = False
        self.io_thread = None
        self.sender_thread = None

        self.data = queue.SimpleQueue()
        self.labels = []

        daemon_me = False
        if source.startswith("/dev/cu"):
            self.io_thread = threading.Thread(target=self.serial_rx, args=(port, 115200))
            self.io_thread.setDaemon(daemon_me)
            self.io_thread.start()
            logger.debug(f"thread {self.io_thread.name} started")
        elif source.startswith("udp:"):
            pass
        elif source.startswith("test:"):
            addr = "127.0.0.1"
            port = 10000
            self.io_thread = threading.Thread(target=self.udp_rx, args=(addr, port))
            self.io_thread.setDaemon(daemon_me)
            self.io_thread.start()
            logger.debug(f"thread {self.io_thread.name} started")
            self.test_thread = threading.Thread(
                target=self.udp_tx, args=(100, addr, port)
            )
            self.test_thread.setDaemon(daemon_me)
            self.test_thread.start()
            logger.debug(f"thread {self.test_thread.name} started")

    def stop_rx(self):
        """Stop io thread and test thread if it is running"""
        logger.info("stopping io_thread...")
        self.time_to_die = True
        logger.debug(f"data.qsize:{self.data.qsize()}")
        self.io_thread.join()
        logger.info("stopped io_thread...")
        if self.test_thread is not None:
            self.test_thread.join()
            logger.info("stopped test_thread...")

    def parse_data(self, rawdata):
        rawdata = rawdata.decode("utf8").strip()
        if len(rawdata) == 0:
            return
        logger.debug(f"rx:{rawdata}")
        l = rawdata.rfind(">")
        if l == -1:
            logger.warning("no > delimiter")
            return
        if self.require_brackets:
            r = rawdata.find("<")
            if r == -1:
                logger.warning("no < delimiter")
                return
        else:
            r = len(rawdata[l + 1 :])
        splits = rawdata[l + 1 : r].split(" ")
        try:
            splits = [float(v) for v in splits]
        except ValueError:
            logger.warning(f"failed to convert {splits}")
        self.labels = [str(i) for i in range(len(splits))]
        self.data.put((datetime.datetime.now(), splits))

    def serial_rx(self, port, baudrate):
        self.ser = serial.Serial(port, baudrate, timeout=TIMEOUT)
        self.ser.flushInput()
        logger.debug(f"connected to {port} at {baudrate}")
        while not self.time_to_die:
            self.parse_data(self.ser.readline())
        self.ser.close()
        logger.info("serial_rx done")

    def udp_rx(self, addr, port):
        sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        sock.bind((addr, port))
        sock.settimeout(0.1)
        logger.info(f"listening on {addr}:{port}")
        try:
            while not self.time_to_die:
                rawdata, remote_addr = sock.recvfrom(BUFFSIZE)
                self.parse_data(rawdata)
        except TimeoutError:
            pass
        logger.info("udp_rx done")

    def udp_tx(self, tx_rate, addr, port):
        sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        logger.debug(f"sending test data to {addr}:{port}")
        i = 0
        t0 = time.perf_counter()
        delay = 1/tx_rate
        while not self.time_to_die:
            pc = time.perf_counter()
            dt = ((pc - t0)-delay) * 1e3
            t0 = pc
            msg = f">{i} {dt}<"
            sock.sendto(str.encode(msg), (addr, port))
            time.sleep(delay)
            i += 1
            if i > tx_rate:
                i = 0
        logger.info("udp_tx done")
