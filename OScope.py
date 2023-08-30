#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import matplotlib as mpl
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import CheckButtons, Button
import matplotlib.animation as animation
from matplotlib.lines import Line2D
import numpy as np
import time

logger = logging.getLogger(__name__)


class OScope:
    def __init__(self, lds, width=2):
        plt.set_loglevel(level="warning")
        mpl.rcParams["toolbar"] = "None"
        plt.style.use("bmh")
        fig, ax = plt.subplots(figsize=(8, 6))
        self.fig = fig
        self.ax = ax

        ui_start_x = 0.80
        ui_start_y = 0.05
        ui_max_y = 0.95

        self.fig.subplots_adjust(top=ui_max_y, right=ui_start_x - 0.01, left=0.07, bottom=ui_start_y)
        self.width = width
        self.lds = lds
        self.width = datetime.timedelta(seconds=float(width))
        self.tdata = [datetime.datetime.now()]
        self.ydata = {}  # label -> data
        self.lines = {}  # label -> line
        self.labels = lds.labels
        self.enabled = {label: True for label in self.labels[1:]}
        colors = ["blue", "red", "green", "yellow"]
        i = 0
        for label in self.labels[1:]:
            self.ydata[label] = [0]
            self.lines[label] = Line2D(self.tdata, self.ydata[label], color=colors[i])
            self.ax.add_line(self.lines[label])
            i += 1
        self.ax.set_ylim(-0.1, 1)
        self.ax.set_xlim(self.tdata[0], self.tdata[0] + self.width)
        self.ax.tick_params(which="minor", width=0.75, length=2.5)
        self.ax.xaxis.set_ticks_position("bottom")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%M:%S"))
        self.ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.2))
        self.ax.yaxis.set_minor_locator(ticker.MultipleLocator(5))

        line_colors = [self.lines[label].get_color() for label in self.labels[1:]]
        leg_h = (len(self.labels) - 1) * 0.04
        legend_ax = fig.add_axes([ui_start_x, ui_max_y - leg_h, 0.15, leg_h])
        legend_ax.set_frame_on(False)
        self.legend = CheckButtons(
            ax=legend_ax,
            labels=self.labels[1:],
            actives=[v for v in self.enabled],
            label_props={"color": line_colors},
            frame_props={"edgecolor": line_colors},
            check_props={"facecolor": line_colors},
        )
        self.legend.on_clicked(self.line_select_callback)

        self.fig.text(ui_start_x, ui_start_y + 0.11, "x:")
        xminus_ax = fig.add_axes([ui_start_x + 0.03, ui_start_y + 0.10, 0.03, 0.04])
        self.b_xminus = Button(xminus_ax, "-")
        self.b_xminus.on_clicked(self.xminus)

        xplus_ax = fig.add_axes([ui_start_x + 0.07, ui_start_y + 0.10, 0.03, 0.04])
        self.b_xplus = Button(xplus_ax, "+")
        self.b_xplus.on_clicked(self.xplus)

        self.fig.text(ui_start_x, ui_start_y + 0.06, "mode:")
        self.modes = ["auto", "roll", "trig"]
        self.mode = 0
        mode_ax = fig.add_axes([ui_start_x + 0.06, ui_start_y + 0.05, 0.10, 0.04])
        self.b_mode = Button(mode_ax, self.modes[self.mode])
        self.b_mode.on_clicked(self.cycle_mode)
        for s in ["top", "right", "left", "bottom"]:
            mode_ax.spines[s].set_visible(False)

        quit_ax = fig.add_axes([ui_start_x + 0.1, ui_start_y, 0.08, 0.04])
        self.b_quit = Button(quit_ax, "quit")
        self.b_quit.on_clicked(self.quit)

        self.paused = False
        pause_ax = fig.add_axes([ui_start_x, ui_start_y, 0.08, 0.04])
        self.b_pause = Button(pause_ax, "pause")
        self.b_pause.on_clicked(self.pause_on_clicked)

        self.ax.figure.canvas.draw()

    def show(self):
        self.ani = animation.FuncAnimation(self.fig, self.update, self.lds.get_data, interval=33, blit=True, save_count=100)
        plt.show()

    def update(self, data):
        if len(data) > 0:
            lastt = self.tdata[-1]
            # reset the arrays
            if lastt >= self.tdata[0] + self.width:
                if self.mode == 0:
                    self.tdata = [self.tdata[-1]]
                    for label in self.labels[1:]:
                        self.ydata[label] = [self.ydata[label][-1]]
                elif self.mode == 1:
                    tmax = self.tdata[-1]
                    tmin = tmax - self.width
                    imin = np.searchsorted(self.tdata, tmin)
                    self.tdata = self.tdata[imin:]
                    for label in self.labels[1:]:
                        self.ydata[label] = self.ydata[label][imin:]
                self.ax.set_xlim(self.tdata[0], self.tdata[0] + self.width)
                self.ax.figure.canvas.draw()

            ymin, ymax = self.ax.get_ylim()
            for row in data:
                self.tdata.append(row[0])
                for i in range(1, len(row)):
                    label = self.labels[i]
                    y = row[i]
                    self.ydata[label].append(y)
                    ymax = max(y, ymax)
                    ymin = min(y, ymin)

            for label in self.labels[1:]:
                self.lines[label].set_data(self.tdata, self.ydata[label])
            self.ax.set_ylim(ymin, ymax)

        return self.lines.values()

    def line_select_callback(self, label):
        self.enabled[label] = not self.enabled[label]
        self.lines[label].set_visible(self.enabled[label])
        self.lines[label].figure.canvas.draw_idle()

    def quit(self, event):
        logger.info("Quitting.")
        self.ani.event_source.stop()
        plt.close(self.fig)

    def pause_on_clicked(self, event):
        self.paused = not self.paused
        if self.paused:
            self.ani.event_source.stop()
            self.b_pause.label.set_text("paused")
        else:
            self.ani.event_source.start()
            self.b_pause.label.set_text("pause")
        self.b_pause.ax.draw(self.fig.canvas.renderer)
        self.fig.canvas.blit(self.b_pause.ax.bbox)

    def cycle_mode(self, event):
        self.mode += 1
        if self.mode >= len(self.modes):
            self.mode = 0
        logger.debug(f"mode:{self.mode}")
        self.b_mode.label.set_text(self.modes[self.mode])
        self.b_mode.ax.draw(self.fig.canvas.renderer)
        self.fig.canvas.blit(self.b_mode.ax.bbox)

    def xminus(self, event):
        self.width = self.width / 5
        pass

    def xplus(self, event):
        pass
