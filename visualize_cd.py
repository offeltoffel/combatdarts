# -*- coding: utf-8 -*-

import numpy as np
from matplotlib import pyplot as plt

class Board_plot:
    def __init__(self, azi, rad):
        self.rad = []
        self.azi = []

        for (r, a) in zip(rad, azi):
            a += 900
            if r < 0:  # below bulls eye
                r = abs(r)
                a -= 18000  # revert azimuth (correction for <0 follows below)

            if a > 36000:  # correction of azimuth for <0° or >360°
                a -= 36000
            elif a < 0:
                a += 36000

            self.rad.append(r)
            self.azi.append(np.deg2rad(a/100))

    def new_plot(self):
        fig = plt.gcf()

        timer = fig.canvas.new_timer(interval=4000)  # creating a timer object and setting an interval of 4000 milliseconds
        timer.add_callback(self.close_event)

        axes_coords = [0, 0, 1, 1]
        pic = plt.imread('Board_cd.png')
        ax_image = fig.add_axes(axes_coords, label="__")
        ax_image.imshow(pic, alpha=1)
        ax_image.axis('off')  # don't show the axes ticks/lines/etc. associated with the image
        ax_image.grid(False)

        ax_polar = fig.add_axes(axes_coords, projection='polar', label="_")
        plt.tick_params(axis="both", which="both", bottom="off", top="off", labelbottom="off", left="off", right="off",
                        labelleft="off")
        plt.axis('off')
        ax_polar.scatter(self.azi, self.rad, marker="x", color="blue")
        ax_polar.set_ylim(0, 25000)
        ax_polar.set_xlim(0, 2 * np.pi)
        ax_polar.axis('off')  # don't show the axes ticks/lines/etc. associated with the image
        ax_polar.grid(False)
        ax_polar.set_theta_offset(0.5 * np.pi)
        ax_polar.set_theta_direction(direction=-1)

        timer.start()
        plt.show()

    def close_event(self):
        plt.close()

if __name__ == '__main__':
    rad = np.asarray([10000, 11000, 5000])
    azi = np.asarray([35200, 0, 10000])
    bp = Board_plot(rad=rad, azi=azi)
    bp.new_plot()
