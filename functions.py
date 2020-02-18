# -*- coding: utf-8 -*-

import numpy as np
import datetime
import pickle
import warnings
import scipy.interpolate as scy_inp
import parameters as par
import outshots


def calc_weights(depth):
    dists = np.arange(1, depth + 1)
    weights = 1 / dists  # derzeit: linear; evtl mit Potenz zwischen 1 und 2? Mehr Gewicht auf vergangenem Wurf
    norm_weights = weights / np.sum(weights)
    return norm_weights


def save_game(ml):
    # save_object = self.scores[:], self.current_player, self.hiscore_evolution, ml.stats_dict, ml.x01, ml.nsets, \
    #               ml.nlegs, ml.player_scores, ml.wins, ml.legs_needed, ml.active_players
    save_object = ml.STORE_list
    now = datetime.datetime.now()
    timestamp_str = "{:4d}{:02d}{:02d}_{:02d}-{:02d}-{:02d}".format(now.year, now.month, now.day, now.hour,
                                                                    now.minute, now.second)
    with open(timestamp_str + '.sav', 'wb+') as f:
        pickle.dump(save_object, f, pickle.HIGHEST_PROTOCOL)

def calc_pressure():
    ## PRESSURE DELTA
    # Calculate pressure factors from arbitrary pressure units
    warnings.filterwarnings('ignore') # result of spline is ill-conditioned -> ignore warning
    cs = scy_inp.CubicSpline(par.pressure_delta_x, par.pressure_delta_y)
    pressure_delta = cs(np.arange(par.n_pressure_interpolation))
    warnings.filterwarnings('default')

    max_prec = np.linspace(start=par.min_pressure, stop=par.max_pressure, num=par.n_pressure_levels)
    ylog = np.log10(np.arange(1, par.pressure_score_max+1))
    y_std = (ylog - ylog.min(axis=0)) / (ylog.max(axis=0) - ylog.min(axis=0))  # transform to range 1.0 to 1.3
    pressure_log = (1 / (np.outer((max_prec - 1.0), y_std) + 1.0))
    return pressure_delta, pressure_log


def calc_experiment():
    # Calculate probabilities for experimentation
    m = np.array(np.arange(start=par.min_experiment, stop=par.max_experiment, step=par.step_experiment))[:, None]

    # Function to scale distributions:
    # F(x) = C * exp(-option/sensitivity parameter), C is scaling factor
    experiment_matrix = list()
    experiment_matrix.append(np.exp(-np.array([1.0]) / m))
    experiment_matrix.append(np.exp(-np.array([1.0, 2.0]) / m))
    experiment_matrix.append(np.exp(-np.array([1.0, 2.0, 3.0]) / m))
    experiment_matrix.append(np.exp(-np.array([1.0, 2.0, 3.0, 4.0]) / m))

    for i in range(4):
        row_sums = experiment_matrix[i].sum(axis=1, keepdims=True)
        experiment_matrix[i] /= row_sums

    return experiment_matrix


def calc_self_cor(n, whos_a_bot):
    # Calculate self-correlations for volatility
    self_corr_vol = [[[], []] for _ in range(n)] # first item is upcoming self_corr_vol, second item is passed self_corr
    sigma_e = np.sqrt((par.self_corr_sigma ** 2) * (1 - par.self_corr ** 2))

    for i in whos_a_bot:
        normal_mean = 0
        signal = [np.random.normal(normal_mean, sigma_e)]
        for _ in range(1, par.self_corr_n_samples):
            normal_mean = signal[-1] / par.draw_towards_zero_coeff
            signal.append(par.self_corr * signal[-1] + np.random.normal(normal_mean, sigma_e))
        self_corr_vol[i][0] = np.array(signal) + 1  # +1 is the offset for µ=1

    return self_corr_vol


def calc_precisions():
    vprec = np.vstack((np.linspace(par.vprec_max[0], par.vprec_min[0], par.n_levels),
                       np.linspace(par.vprec_max[1], par.vprec_min[1], par.n_levels),
                       np.linspace(par.vprec_max[2], par.vprec_min[2], par.n_levels),
                       np.linspace(par.vprec_max[3], par.vprec_min[3], par.n_levels)))

    hprec = np.vstack((np.linspace(par.hprec_max[0], par.hprec_min[0], par.n_levels),
                       np.linspace(par.hprec_max[1], par.hprec_min[1], par.n_levels),
                       np.linspace(par.hprec_max[2], par.hprec_min[2], par.n_levels),
                       np.linspace(par.hprec_max[3], par.hprec_min[3], par.n_levels)))

    boost_score = np.linspace(par.boost_max, par.boost_min, par.n_levels_special)
    boost_co = np.linspace(par.boost_max, par.boost_min, par.n_levels_special)

    return vprec, hprec, boost_score, boost_co


def score_from_field(hit_str):
    field = hit_str[0]
    num = int(hit_str[1:])
    factor = outshots.field_factors[field]
    return factor * num