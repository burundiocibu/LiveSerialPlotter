#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import datetime
import logging
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import CheckButtons, Button
import numpy as np

logger = logging.getLogger(__name__)


class OScope:
    def __init__(self, args):
        plt.set_loglevel(level="warning")
        self.x_width = datetime.timedelta(seconds=int(args.window_size))
        plt.ion()
        self.tmax = datetime.datetime.now()
        self.imin = 0
        self.labels = []
        self.enabled = {} # labels -> enabled
        self.lines = {} # labels->lines
        self.paused = False
        self.time_to_die = False

    def set_labels(self, labels):
        if not self.labels == labels:
            self.labels = labels
            self.enabled = {label:True for label in self.labels[1:]}

    def line_select_callback(self, label):
        self.enabled[label] = not self.enabled[label]
        self.lines[label][0].set_visible(self.enabled[label])
        self.lines[label][0].figure.canvas.draw_idle()

    def quit(self, event):
        self.time_to_die = True
        logger.info("Quitting.")


    def pause(self, event):
        self.paused = not self.paused


    def makeFig(self, data):
        if len(data) < 1:
            return
        d = np.array(data).T
        t = d[0]
        tmax = t[-1]
        if tmax <= self.tmax or self.paused:
            plt.pause(0.001)
            return
        
        self.tmax = tmax
        tmin = t[-1] - self.x_width
        plt.clf()
        plt.grid(True, which="both", axis='both')
        fig = plt.gcf()
        fig.subplots_adjust(top=.95, right=0.8, left=0.075)

        ax = plt.gca()
        ax.set_xlim(tmin, tmax)
        ax.tick_params(which="minor", width=0.75, length=2.5)
        ax.xaxis.set_ticks_position("bottom")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%M:%S"))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.2))
        ax.yaxis.set_minor_locator(ticker.MultipleLocator(5))
        for i in range(1, len(self.labels)):
            label = self.labels[i]
            self.lines[label] = ax.plot(t, d[i], "-", visible=self.enabled[label], label=label)

        line_colors = [self.lines[label][0].get_color() for label in self.labels[1:]]
        legend_ax = fig.add_axes([0.81, 0.8, 0.1, 0.15])
        legend_ax.set_frame_on(False)
        self.legend = CheckButtons(
            ax=legend_ax,
            labels=self.labels[1:],
            actives=[v for v in self.enabled],
            label_props={'color': line_colors},
            frame_props={'edgecolor': line_colors},
            check_props={'facecolor': line_colors},
        )
        self.legend.on_clicked(self.line_select_callback)

        quit_ax = fig.add_axes([0.81, 0.05, 0.05, 0.05])
        self.b_quit = Button(quit_ax, "Quit")
        self.b_quit.on_clicked(self.quit)

        self.imin = np.searchsorted(t, tmin)
        plt.pause(0.001)
