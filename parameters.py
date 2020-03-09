# -*- coding: utf-8 -*-

import numpy as np

######## Careful changing of the parameters!

## PRECISION
vprec_max = [4000, 4000, 3700, 5000] # lowest vertical precision for [Triples, Singles, Doubles, Bull] (std of aim) 
vprec_min = [550, 650, 550, 525] # highest vertical precision for [Triples, Singles, Doubles, Bull] (std of aim)

hprec_max = [1300, 1300, 1300, 1400] # lowest horizontal precision for [Triples, Singles, Doubles, Bull] (std of aim)
hprec_min = [135, 140, 135, 145] # lowest horizontal precision for [Triples, Singles, Doubles, Bull] (std of aim) 

boost_max = 1.0
boost_min = 0.8

n_levels = 50 # levels of precision (1 == highest, 50 == lowest)
n_levels_special = 6 # levels of speciality (1 == lowest, 6 == highest)
## /PRECISION


## PRESSURE
pressure_delta_x = [0, 250, 500] # X-Values of spline (Stützpunkte)
pressure_delta_y = [0, 100, 0] # Y-Values of spline (Stützpunkte)
n_pressure_interpolation = 501 # Density of the interpolation (n points on graph)

min_pressure = 1.0
max_pressure = 1.3
n_pressure_levels = 26

pressure_score_max = 170 # highest score at which pressure for opponent occurs (def: 170)
## /PRESSURE


## EXPERIMENTATION
min_experiment = 0.1
max_experiment = 5.1
step_experiment = 0.1
## /EXPERIMENTATION



## SELF CORRELATION
self_corr_n_samples = 300  # maximum is 300 visits, afterwards: calc new
self_corr = 0.999  # must not exceed 1! 0.999 as default
self_corr_sigma = 0.2  # 0.2 as default!
draw_towards_zero_coeff = -50  # weights for dragging the signal back towards zero; the lower, the stronger
## /SELF CORRELATION


## YES / NO
# Words or letters that cause a positive reaction
yes = ["yes", "y", "yeah", "true", "1", "ja", "si", "oui"]
no = ["no", "n", "nope", "false", "0", "nein", "non"]

## BOT SLEEP
# How long does bot sleep when delay is TRUE?
bot_sleep = 1.0 # seconds