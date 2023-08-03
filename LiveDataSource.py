# -*- coding: utf-8 -*-
"""
This class takes care of getting up-to-date data. It spawns off a thread to keep
some np arrays up-to-date and also provides some tk callbacks to configure it.

It accepts data from either a serial port or from a udp socket.
"""
from argparse import Namespace
import asyncio
import glob
import logging
import numpy as np
import queue
import serial
import sys
import threading

logger = logging.getLogger(__name__)

TIMEDELAY = 100  # Milliseconds between getting new data


class LiveDataSource():
    def __init__(self, args: Namespace, window):
        super().__init__()
        self.ser = None
        self.master = window.master
        self.window = window
        self.IS_SERIAL_CONNECTED = False
        self.printRawData = False

        self.refreshSerial()
        menu = self.window.baudrateoptionmenu["menu"]
        menu.delete(0, "end")
        baud_rates = [110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000]
        for v in baud_rates:
            menu.add_command(label=str(v), command=lambda value=str(v): self.om_variable.set(value))

        self.window.connectbutton["command"] = self.connectToSerial
        self.window.disconnectbutton["command"] = self.disconnectFromSerial
        self.window.refreshserialbutton["command"] = self.refreshSerial

        self.queue = queue.Queue()
        self.window.queue = queue
        self.io_thread = None

    # =============================================================================
    # This function comes graciously from StackOverflow
    # Finds all available serial ports, and returns as a list.
    def findAllSerialPorts(self):
        if sys.platform.startswith("win"):
            ports = ["COM%s" % (i + 1) for i in range(256)]
        elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob("/dev/tty[A-Za-z]*")
        elif sys.platform.startswith("darwin"):
            # This only works on "newer" OSX releases
            ports = glob.glob("/dev/cu.usb*")
        else:
            raise EnvironmentError("Unsupported platform")
        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except:
                logger.warning(f"Error opening {port}")
        return result

    # =============================================================================
    # Closes all serial ports.
    def closeAllSerialPorts(self):
        ports = self.findAllSerialPorts()
        for p in ports:
            try:
                p.close()
            except:
                continue
        self.IS_SERIAL_CONNECTED = False

    # =========================================================================
    # Connects GUI to a COM port based on the user selected port.
    def connectToSerial(self):
        try:
            port = self.window.portentrystr.get()
            baudrate = int(self.window.baudrateentrystr.get())
            logger.debug("Connecting to %s at %d" % (port, baudrate))
            self.ser = serial.Serial(port, baudrate, timeout=1)
            self.ser.flushInput()
        except:
            logger.warn(f"Could not connect to {port}")
            self.toggleSerialConnectedLabel(False)
            return -1

        self.IS_SERIAL_CONNECTED = True  # Set GUI state
        self.toggleSerialConnectedLabel(True)  # Show the state
        logger.debug("Connected")
        self.io_thread = threading.Thread(target=self.run)
        self.io_thread.start()
        logger.debug(f"thread {self.io_thread.name} started")

    # =========================================================================
    # Disconnects from whatever serial port is currently active.
    def disconnectFromSerial(self):
        logger.info("Disconnecting")
        if self.IS_SERIAL_CONNECTED:  # Only do this if already connected.
            self.ser.close()
            self.toggleSerialConnectedLabel(False)
            self.IS_SERIAL_CONNECTED = False
        if self.io_thread is not None:
            self.io_thread.join()

    # =========================================================================
    # Swap out the string label indicating whether serial is connected.
    def toggleSerialConnectedLabel(self, connection):
        if connection:
            self.window.serialconnectedstringvar.set("Connected")
            self.window.serialconnectedlabel.config(fg="green")
        else:
            self.window.serialconnectedstringvar.set("Unconnected")
            self.window.serialconnectedlabel.config(fg="red")

    # =========================================================================
    # Refreshes the list of available serial ports on the option menu.
    def refreshSerial(self):
        new_serial_list = self.findAllSerialPorts()

        logger.info("Refreshing serial port list")
        if len(new_serial_list) == 0:
            logger.warn("No available serial ports.")
            return

        self.window.portentrystr.set(new_serial_list[-1])  # Set the variable to none
        self.window.portoptionmenu["menu"].delete(0, "end")  # Delete the old list

        for port in new_serial_list:
            logger.debug(f"Adding {port}")
            self.window.portoptionmenu["menu"].add_command(label=port, command=lambda v=port: self.om_variable.set(v))


    # =========================================================================
    # Changes the "good data received" indicator.
    def setPackageIndicator(self, state):
        if state == "good":
            self.window.packageindicator.set("!")
            self.window.packageindicatorlabel.config(fg="green", font=("times", 20, "bold"))
        else:
            self.window.packageindicator.set(".")
            self.window.packageindicatorlabel.config(fg="black", font=("times", 20, "bold"))

    # =========================================================================
    def run(self):
        while self.IS_SERIAL_CONNECTED:
            rawdata = self.ser.readline().decode("utf8").strip()
            if len(rawdata) == 0:
                continue
            if self.window.printrawdata.get():
                logger.info(rawdata)
            l = rawdata.rfind(">")
            if l == -1:
                logger.warning("No > delimiter")
                self.setPackageIndicator("bad")
                continue
            if self.window.requirebrackets.get():
                r = rawdata.find("<")
                if r == -1:
                    logger.warning("No < delimiter")
                    self.setPackageIndicator("bad")
                    continue
            else:
                r = len(rawdata[l + 1 :])
            splits = rawdata[l + 1 : r].split(" ")
            try:
                splits = [float(v) for v in splits]
                self.setPackageIndicator("good")
            except ValueError:
                logger.warning(f"Failed to convert {splits}")
                self.setPackageIndicator("bad")

            self.window.data.append(splits)
