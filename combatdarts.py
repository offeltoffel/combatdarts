# -*- coding: utf-8 -*-
import os
import sys
import numpy as np
import scipy.interpolate as scy_inp
import outshots
import visualize_cd as vcd
from matplotlib import pyplot as plt
import time
from copy import deepcopy
import pickle

from functions import *
import parameters as par

path = os.path.dirname(os.path.abspath(__file__))

class GameOn:
    def __init__(self, main, load_paras=None):
        self.m = main
        self.init_game(load_paras=load_paras)
        self.outshot_dict = [outshots.co_dict_n3, outshots.co_dict_n2, outshots.co_dict_n1]
        self.player_string = None
        self.rewind_scores = [list() for _ in range(self.m.ml.nplayers)]
        self.skills_txt = ["vprec", "hprec", "special", "boost", "mental", "exp"]
        self.calc_skills()
        self.assign_skills()
        self.abort = False
        self.attempts = 0
        self.game_loop()

    def init_game(self, load_paras=None):
        if load_paras:  # loaded game
            self.scores = deepcopy(load_paras[0])
            self.current_player = load_paras[1]
            self.hiscore_evolution = deepcopy(load_paras[2])
            self.self_corr_vol = deepcopy(load_paras[3])
        else:  # new game
            self.scores = [self.m.ml.x01 for _ in range(self.m.ml.nplayers)]
            self.current_player = 0
            self.hiscore_evolution = [[list(), list(), list(), list()] for _ in range(self.m.ml.nplayers)]  # [["leg, set, match, ever"] for nplayers
            self.self_corr_vol = None
            for pl in range(self.m.ml.nplayers):
                for i in range(4):
                    self.hiscore_evolution[pl][i].append(self.m.ml.stats_dict[pl]['HiScore'][i + 1])

    def calc_skills(self):
        self.vprec, self.hprec, self.boost_score, self.boost_co = calc_precisions()  # Precision for complex bot
        self.pressure_delta, self.pressure_log = calc_pressure()   # Pressure for complex bot according to delta
        self.experiment_matrix = calc_experiment()  # Calculate probabilities for experimentation
        if not self.self_corr_vol: # if self_corr_vol was loaded, skip its calculation
            self.self_corr_vol = calc_self_cor(n=self.m.ml.nplayers, whos_a_bot=self.m.ml.whos_a_bot)  # Calculate Self Correlation (Bot Volatility)
            # Structure of self.self_corr_vol: [a][b]; a = player# (0, 1, ...); b = [upcoming_self_corr_vals, passed self_corr_vals]

    def assign_skills(self):
        self.skills = []
        self.pressure_factors = []
        for pl in range(self.m.ml.nplayers):
            temp = [int(element)-1 for element in self.m.ml.players_dict[pl][2].split(',')]
            if len(temp) == 1:
                temp *= 6
            else:
                temp[4] += 1  # mental strength is -25 to +25, no shift -1
            self.skills.append(dict(zip(self.skills_txt, temp)))
            self.pressure_factors.append(self.pressure_log[abs(self.skills[pl]['mental'])])
        self.scales_rad = [None for _ in range(self.m.ml.nplayers)]  # scales for each player, no matter if bot or not
        self.scales_azi = [None for _ in range(self.m.ml.nplayers)]

        for pl in [i for i in range(self.m.ml.nplayers) if i in self.m.ml.whos_a_bot]:  # assign precisions for bots only
            if self.skills[pl]['special'] == 1:  # score leaning
                special_score = self.m.ml.boost_score[self.skills[pl]['special']]
                special_co = 1/special_score
            elif self.skills[pl]['special'] == 2:  # CO-leaning
                special_co = self.boost_score[self.skills[pl]['special']]
                special_score = 1/special_co
            else:  # None
                special_co = 1
                special_score = 1
            self.scales_rad[pl] = {"T": self.vprec[0, self.skills[pl]['vprec']]*special_score,
                                   "S": self.vprec[1, self.skills[pl]['vprec']]*special_score,
                                   "D": self.vprec[2, self.skills[pl]['vprec']]*special_co,
                                   "B": self.vprec[3, self.skills[pl]['vprec']]*special_co}

            self.scales_azi[pl] = {"T": self.hprec[0, self.skills[pl]['hprec']]*special_score,
                                   "S": self.hprec[1, self.skills[pl]['hprec']]*special_score,
                                   "D": self.hprec[2, self.skills[pl]['hprec']]*special_co,
                                   "B": self.hprec[3, self.skills[pl]['hprec']]*special_co}

    def assign_pressure(self):  # turned off if nplayers > 2
        pl = self.current_player
        opp = abs(pl-1)  # opponent player, works only for nplayers = 2
        recent_score_opponent = self.scores[opp]
        score_deltas = []
        nscores = [len(self.m.ml.player_scores[i][0]) for i in [0, 1]]

        # Calculate inverse-distance-weighted delta (n=3)
        for k in range(nscores[pl]+1):
            score_deltas.append(self.m.ml.STORE_list[-(k*2+1)][0][pl] - self.m.ml.STORE_list[-(k*2+1)][0][opp])
            if k == 3:
                break  # just watch the last four entries (3: deltas, 4: delta of deltas)

        norm_weights = [calc_weights(depth=i) for i in range(1, 5)]
        # weighted_delta = np.sum(norm_weights[len(score_deltas)-1] * np.asarray(score_deltas)) # deactivated

        # Calculate delta of inverse-distance-weighted deltas (n=3)
        n_weighted_delta = len(score_deltas)
        if n_weighted_delta > 1:
            delta_deltas = [score_deltas[i] - score_deltas[i+1] for i in range(n_weighted_delta-1)]
            weighted_delta_deltas = np.sum(norm_weights[len(delta_deltas)-1] * np.asarray(delta_deltas))
        else:
            weighted_delta_deltas = 0.0

        # Obtain pressure through distance between players
        if score_deltas[0] > 0:  # score_deltas[0] is current score delta. positive value: opponent leads
            pressure_delta = self.m.ml.pressure_delta[score_deltas[0]]
        else:
            pressure_delta = 0.0

        # self.m.pr(weighted_delta)
        # Ein Index (Integer), der angibt, wie nah die Spieler in den letzten Aufnahmen
        # beisammen waren, wobei der letzte Spielstand am stärksten und der viertletzte am niedrigsten
        # gewichtet wird
        # Negativ = Der Spieler liegt in Führung
        # Positiv = Der Gegner liegt vorne

        # self.m.pr(weighted_delta_deltas)
        # Ein Index (Integer), der angibt, wie sich die Abstände der Spieler mit der Zeit verändert haben
        # wobei die neuste Änderung am stärksten und die drittletzte am niedrigsten gewichtet wird
        # Negativ = Man konnte sich vom Gegner absetzen (oder den Rückstand verringern)
        # Positiv = Der Gegner konnte sich absetzen (oder den Rückstand verringern)

        if recent_score_opponent in [8, 16, 24, 32, 40]:
            opp_pressure = 100
        elif recent_score_opponent in [4, 12, 20, 28, 36]:
            opp_pressure = 90
        elif recent_score_opponent in [2, 6, 10, 14, 18, 22, 26, 30, 34, 38]:
            opp_pressure = 85
        elif recent_score_opponent < 61:
            opp_pressure = 80
        elif recent_score_opponent < 81:
            opp_pressure = 75
        elif recent_score_opponent < 101:
            opp_pressure = 70
        elif recent_score_opponent < 131:
            opp_pressure = 60
        elif recent_score_opponent < 171:
            if recent_score_opponent in [169, 168, 166, 165, 163, 162, 159]:
                opp_pressure = 30
            else:
                opp_pressure = 50
        else:
            opp_pressure = 0

        pressure = opp_pressure + weighted_delta_deltas + pressure_delta
        return pressure

    def make_image(self):
        ml = self.m.ml
        image_object = (self.scores[:], self.current_player, deepcopy(self.hiscore_evolution), deepcopy(ml.players_dict),
                        deepcopy(ml.stats_dict), ml.x01, ml.nsets, ml.nlegs, deepcopy(ml.player_scores),
                        deepcopy(ml.wins), ml.legs_needed, ml.active_players, deepcopy(self.self_corr_vol), deepcopy(ml.BOT_hits))
        ml.STORE_list.append(image_object)

    def call_image(self, ii, direction="from_STORE"):
        ml = self.m.ml
        if direction == "from_STORE":  # Call attributes from STORE_list into current game (rewind)
            image_object = ml.STORE_list[-ii]
        else:  # Call attributes from STORE_REWIND_list into current game (restore)
            image_object = ml.REWIND_STORE_list[-ii]
        self.scores = image_object[0][:]
        self.current_player = image_object[1]
        self.hiscore_evolution = deepcopy(image_object[2])
        ml.players_dict = deepcopy(image_object[3])
        ml.stats_dict = deepcopy(image_object[4])
        ml.x01 = image_object[5]
        ml.nsets = image_object[6]
        ml.nlegs = image_object[7]
        ml.player_scores = deepcopy(image_object[8])
        ml.wins = deepcopy(image_object[9])
        ml.legs_needed = image_object[10]
        ml.active_players = image_object[11]
        self.self_corr_vol = deepcopy(image_object[12])
        _ = image_object[13]  # BOT_hits is NOT restored (we need BOT_hits for the rewind)

    def game_loop(self):
        self.current_player = (self.m.ml.leg % self.m.ml.nplayers +
                               self.m.ml.set % self.m.ml.nplayers) % self.m.ml.nplayers
        self.make_image()  # new image at the beginning of each leg
        self.m.pr("******")
        self.m.pr(self.print_matchscore())
        while True:
            player = self.current_player
            self.attempts = 0
            self.player_string = "\t{:d} --> ".format(self.scores[player])
            if player not in self.m.ml.whos_a_bot:
                game_input = input("Player {:d} ({}): {:d} {} >>> ".format(player + 1,
                                                                           self.m.ml.players_dict[player][0],
                                                                           self.scores[player],
                                                                           self.suggestion(score=self.scores[player])))
            else:  # 'Bot'
                if self.bot_score() == "checkout":
                    continue_flag = False  # Kopie von Close-Procedure unten -> bessere Lösung?
                    if any(self.m.ml.wins[pl][2] == self.m.ml.nsets for pl in range(self.m.ml.nplayers)):
                        self.make_image()  # Usually no image is created at the end of the leg, but here we need a current state to rewind
                        while True:
                            self.m.pr("***")
                            if not self.m.ml.autoplay:
                                finish_input = input("Close this match? (y=yes, n=no/rewind) >>> ")
                            else:
                                finish_input = "y"
                            if finish_input.lower() in par.yes:
                                break
                            elif finish_input.lower() in par.no:
                                continue_flag = True
                                self.invoke_rewind()
                                break
                    if continue_flag:
                        continue
                    else:
                        break
                else:
                    continue

            if "+" in game_input:
                try:
                    self.attempts = int(game_input.split('+')[1])
                    if self.attempts > 3:
                        attempt_error = "Got {:d} unsuccessful checkout attempts. Continue anyway? y/n >>> ".format(self.attempts)
                    elif self.scores[player] > 170:
                        attempt_error = "Got checkout attempts at score {:d}. Continue anyay? y/n >>> ".format(self.scores[player])
                    else:
                        attempt_error = None

                    if attempt_error:
                        while True:
                            answer = input(attempt_error)
                            if answer.lower() in par.yes:
                                proceed = True
                                break
                            elif answer.lower() in par.no:
                                proceed = False
                                break
                        if not proceed:
                            continue

                except ValueError:
                    self.m.pr("#!# unexpected input for unsuccessful attempts: '{}'".format(game_input.split('+')[1]))
                    continue
                game_input = game_input.split('+')[0]

            try:
                game_input = int(game_input)
                if game_input > 180 or self.scores[player] - game_input <= 1:
                    while True:
                        answer = input("\tInvalid score of {:d}! Proceed anyway? y/n >>> ".format(game_input))
                        if answer.lower() in par.yes:
                            proceed = True
                            break
                        elif answer.lower() in par.no:
                            proceed = False
                            break
                    if not proceed:
                        continue

                self.scoring(player=player, score=game_input, mode='regular')
                continue

            except ValueError:
                if game_input.startswith("c"):
                    ndarts = game_input[1:]
                    try:
                        ndarts = int(ndarts)
                    except ValueError:
                        if ndarts == "":
                            ndarts = 1
                        else:
                            print("#!# unexpected checkout: '%s'" % ndarts)
                            continue

                    if self.scores[player] > 170 or ndarts > 3 \
                            or not self.scores[player] in outshots.is_checkable_with_x[ndarts-1]:
                        while True:
                            answer = input("\tInvalid checkout of score {:d} with {:d} darts. Proceed anyway? y/n >>> ".format(self.scores[player], ndarts))
                            if answer.lower() in par.yes:
                                proceed = True
                                break
                            elif answer.lower() in par.no:
                                proceed = False
                                break
                        if not proceed:
                            continue
                    self.checkout(ndarts=ndarts)  # now proceed to checkout

                    continue_flag = False
                    if any(self.m.ml.wins[pl][2] == self.m.ml.nsets for pl in range(self.m.ml.nplayers)):
                        self.make_image()  # Usually no image is created at the end of the leg, but here we need a current state to rewind
                        while True:
                            self.m.pr("***")
                            finish_input = input("Close this match? (y=yes, n=no/rewind) >>> ")
                            if finish_input.lower() in par.yes:
                                break
                            elif finish_input.lower() in par.no:
                                continue_flag = True
                                self.invoke_rewind()
                                break
                    if continue_flag:
                        continue
                    else:  # Reset BOT rewind lists
                        self.m.ml.BOT_hits = [[] for _ in range(self.m.ml.nplayers)]
                        self.m.ml.bot_rewind_count = [0 for _ in range(self.m.ml.nplayers)]
                        break

                elif game_input == "settings":
                    self.m.ml.settings()
                    continue

                elif game_input == "bot_state":
                    if not self.m.ml.whos_a_bot:
                        self.m.ml.pr("\tNo bot participating in this match!")
                        continue
                    else:
                        for i_bot in self.m.ml.whos_a_bot:
                            len_passed = len(self.self_corr_vol[i_bot][1])
                            plt.plot(range(len_passed), self.self_corr_vol[i_bot][1], linestyle="--", color='orange',
                                     label='Preceeding visits')
                            plt.plot(range(len_passed, len_passed + len(self.self_corr_vol[i_bot][0])), self.self_corr_vol[i_bot][0],
                                     color='orange', label='Upcoming visits')
                            plt.axvline(x=len_passed, color='black', linewidth=0.5)
                            plt.ylabel("Precision factor")
                            plt.xlabel("Visits")
                            plt.title("Volatile precision factors for Player {:d} ({})".format(i_bot+1, self.m.ml.players_dict[i_bot][0]))
                            plt.legend()
                            plt.tight_layout()
                            plt.show()
                            continue

                elif game_input.startswith("hints"):
                    hint_split = game_input.split("#")
                    if len(hint_split) == 1:
                        self.all_suggestions(score=self.scores[player], ndarts=3)
                    else:
                        try:
                            hint_split[1] = int(hint_split[1])
                        except ValueError:
                            self.m.pr("Invalid number of darts for hints: {}".format(hint_split[1]))
                            continue
                        if hint_split[1] < 1 or hint_split[1] > 3:
                            self.m.pr("Invalid number of darts for hints: {:d}".format(hint_split[1]))
                            continue
                        else:
                            if len(hint_split) < 3:
                                self.m.pr("Missing information: Score!")
                                continue
                            try:
                                hint_split[2] = int(hint_split[2])
                            except ValueError:
                                self.m.pr("Invalid score for hints: '{}'".format(hint_split[2]))
                                continue
                            self.all_suggestions(score=hint_split[2], ndarts=hint_split[1])
                    continue

                elif game_input == "save":
                    save_game(ml=self.m.ml)
                    continue

                elif game_input.startswith("stats"):
                    add = game_input[5:]
                    which = None
                    who = None
                    if not add == "":
                        try:
                            who = int(add)
                        except ValueError:
                            if add.startswith('l'):
                                which = 1
                            elif add.startswith('s'):
                                which = 2
                            elif add.startswith('m'):
                                which = 3
                            else:
                                self.m.pr("#!# Try 'stats' with 'l' (leg), 's' (set) or 'm' (match) + player number")
                                continue

                        if not who:
                            if add[1:] == "":
                                who = None
                            else:
                                try:
                                    who = int(add[1:])
                                except ValueError:
                                    self.m.pr(
                                        "#!# Try 'stats' with 'l' (leg), 's' (set) or 'm' (match) + player number")
                                    continue

                    self.m.pr(self.print_stats(which=which, who=who))
                    continue

                elif game_input.startswith("s"):
                    set_score = game_input[1:]
                    try:
                        set_score = int(set_score)
                    except ValueError:
                        print("#!# unexpected score to set: '{}'".format(set_score))
                        set_score = None

                    if set_score:
                        score_visit = self.scores[player] - set_score
                        if score_visit > 180:
                            while True:
                                answer = input("\tInvalid score of {:d}! Proceed anyway? y/n >>> ".format(score_visit))
                                if answer.lower() in par.yes:
                                    proceed = True
                                    break
                                elif answer.lower() in par.no:
                                    proceed = False
                                    break
                            if not proceed:
                                continue
                        self.scoring(player=player, score=set_score, mode='set')
                    else:
                        continue

                elif game_input == "h":
                    score_visit = self.scores[player] // 2
                    if score_visit > 180:
                        while True:
                            answer = input("\tInvalid score of {}! Proceed anyway? y/n >>> ".format(score_visit))
                            if answer.lower() in par.yes:
                                proceed = True
                                break
                            elif answer.lower() in par.no:
                                proceed = False
                                break
                        if not proceed:
                            continue

                    if self.scores[player] % 2 > 0:
                        self.m.pr("\tCannot half an uneven score!")
                        continue
                    self.scoring(player=player, score=None, mode='half')

                elif game_input == "r":
                    self.invoke_rewind()
                    continue

                elif game_input == "f":
                    if len(self.m.ml.REWIND_STORE_list) > 0:
                        next_player = self.m.ml.REWIND_STORE_list[-1][1]
                        self.restore()
                    else:
                        self.m.pr("No score in memory to restore!")
                        continue

                    while len(self.m.ml.REWIND_STORE_list) > 0:
                        if int(self.m.ml.STORE_list[-1][3][next_player][1]) > 1:  # if bot threw last and has a valid score to rewind
                            next_player = self.m.ml.REWIND_STORE_list[-1][1]
                            self.restore()
                        else:
                            break

                    if any(self.m.ml.wins[pl][2] == self.m.ml.nsets for pl in range(self.m.ml.nplayers)):  # happens after rewind on finish
                        break
                    else:
                        continue

                elif game_input == "abort":
                    self.abort = True
                    break
                else:
                    self.m.pr("\tUnknown command: {}".format(game_input))

        if self.abort:
            self.m.start_loop()

    def invoke_rewind(self):
        if len(self.m.ml.STORE_list) > 1:
            self.rewind()
        else:
            self.m.pr("No score in memory to rewind!")
            return

        while len(self.m.ml.STORE_list) > 1:
            last_player = self.m.ml.STORE_list[-1][1]  # meanwhile, STORE_list[-1] = last value (old -1 has been deleted/moved to REWIND_STORE_list)
            if int(self.m.ml.STORE_list[-1][3][last_player][1]) > 1:  # if bot threw last and has a valid score to rewind
                self.m.ml.bot_rewind_count[last_player] += 1
                self.rewind()
            else:
                break

    def rewind(self):
        ml = self.m.ml
        player = ml.STORE_list[-2][1]  # STORE_list -1 = current, -2 = last
        ml.REWIND_STORE_list.append(list())
        for item in ml.STORE_list[-1]:
            ml.REWIND_STORE_list[-1].append(deepcopy(item))
        self.call_image(ii=2, direction='from_STORE')  # restores REWIND_STORE_list[-ii][:]
        wins_old = ml.REWIND_STORE_list[-1][9]
        if not all(wins_old[i][2] == ml.wins[i][2] for i in range(ml.nplayers)):
            print_str = "\trewinding to Sets: {:d}".format(ml.wins[0][2])
            for pl_num in range(1, ml.nplayers):
                print_str += " - {:d}".format(ml.wins[pl_num][2])
            self.m.pr(print_str)
            ml.set -= 1
            ml.sets_won_before -= 1
        if not all(wins_old[i][1] == ml.wins[i][1] for i in range(ml.nplayers)):
            print_str = "\trewinding to Legs: {:d}".format(ml.wins[0][1])
            for pl_num in range(1, ml.nplayers):
                print_str += " - {:d}".format(ml.wins[pl_num][1])
            self.m.pr(print_str)
            ml.leg -= 1
            if ml.whos_a_bot:  # check for bots in game
                if not all(wins_old[i][1] == ml.wins[i][1] for i in ml.whos_a_human):  # Human had checked the leg, bot needs new throw
                    ml.BOT_hits = [[] for _ in range(ml.nplayers)]
                    ml.bot_rewind_count = [0 for _ in range(ml.nplayers)]

        self.m.pr("\t{} rewinding to Score: {:d} --> {:d}".format(ml.players_dict[player][0],
                                                                  ml.REWIND_STORE_list[-1][0][player],
                                                                  self.scores[player]))

        del ml.STORE_list[-1]
        self.current_player = player

    def restore(self):
        ml = self.m.ml
        player = self.current_player
        if player in ml.whos_a_bot:
            ml.bot_rewind_count[player] -= 1
        old_score = self.scores[player]
        wins_old = np.array([[ml.wins[i][1], ml.wins[i][2]] for i in range(ml.nplayers)])
        ml.STORE_list.append(list())
        for item in ml.REWIND_STORE_list[-1]:
            ml.STORE_list[-1].append(deepcopy(item))
        self.call_image(ii=1, direction='from_REWIND')

        if not all(wins_old[i][1] == ml.wins[i][2] for i in range(ml.nplayers)):
            print_str = "\trestoring to Sets: {:d}".format(ml.wins[0][2])
            for pl_num in range(1, ml.nplayers):
                print_str += " - {:d}".format(ml.wins[pl_num][2])
            self.m.pr(print_str)
        if not all(wins_old[i][0] == ml.wins[i][1] for i in range(ml.nplayers)):
            print_str = "\trestoring to Legs: {:d}".format(ml.wins[0][1])
            for pl_num in range(1, ml.nplayers):
                print_str += " - {:d}".format(ml.wins[pl_num][1])
            self.m.pr(print_str)

        self.m.pr("\t{} restoring to Score: {:d} --> {:d} ".format(ml.players_dict[player][0], old_score, self.scores[player]))
        self.current_player = ml.REWIND_STORE_list[-1][1]
        del ml.REWIND_STORE_list[-1]

    def bot_score(self):
        player = self.current_player
        botcnt = self.m.ml.bot_rewind_count[player]
        total_botscore = 0
        score = self.scores[player]
        out_dicts = [outshots.co_dict_n1, outshots.co_dict_n2, outshots.co_dict_n3]

        self.m.pr("\nPlayer {:d} ({}): {:d} ...".format(player + 1,
                                                        self.m.ml.players_dict[player][0],
                                                        self.scores[player]))

        signum = np.sign(self.skills[player]['mental'])
        if signum != 0 and self.m.ml.settings_dict['psychmod'][1] == 1 and self.m.ml.nplayers == 2:
            pressure = self.assign_pressure()  # get pressure
        else:
            pressure = 0

        vol_fac = self.self_corr_vol[player][0][0]  # basic volatility from distribution  # nplayer
        self.self_corr_vol[player][1].append(vol_fac)
        if len(self.self_corr_vol[player][0]) < 2:
            calc_self_cor(n=self.m.ml.nplayers, whos_a_bot=self.m.ml.whos_a_bot)  # calculate a new distribution - should never happen in a standard game
        else:
            self.self_corr_vol[player][0] = np.delete(self.self_corr_vol[player][0], 0)  # truncate first item in distrib.

        # self.m.pr("current vol_fac: ", vol_fac)
        if vol_fac < 0.9:
            self.m.pr("Bot says: Hell yeah, I'm on fire!")
        elif vol_fac > 1.1:
            self.m.pr("Bot says: Don't feel too well...")

        bot_hits = [list(), list()]
        for k, ndarts in enumerate(range(2, -1, -1)):
            if score > 230:
                aim = "T20"
            else:  # choose one of the options for the score!
                n_options = len(out_dicts[ndarts][score])  # how many options for this score?
                # get probabilities for n_options and experiment_level
                probabilites = self.experiment_matrix[n_options-1][self.skills[player]['exp']]
                # draw an option according to probabilities for n_options available
                option = np.random.choice(np.arange(start=0, stop=n_options, step=1), p=probabilites)
                aim = out_dicts[ndarts][score][option]  # aim at that option

            if not self.m.ml.autoplay:
                sys.stdout.write("\t{:>7}: ".format("({})".format(aim)))
                sys.stdout.flush()  # writes the output and allows next print to be in same line

            if self.m.ml.settings_dict['bottime'][1] == 1:
                time.sleep(par.bot_sleep)

            aim_field = aim[0]
            aim_num = int(aim[1:])

            if signum != 0 and self.m.ml.settings_dict['psychmod'][1] == 1 and self.m.ml.nplayers == 2:
                total_pressure = pressure
                if (aim_field == "D" and score == aim_num * 2) or (aim_field == "B50" and score == 50):  # co attempt
                    total_pressure += 10
                    if self.m.ml.wins[player][1] == self.m.ml.legs_needed - 1:  # leg to win set; does not work for nplayers > 2
                        total_pressure += 20
                        if self.m.ml.wins[player][2] == self.m.ml.nsets - 1:  # set to win match
                            total_pressure += 20

                if total_pressure < 0:
                    total_pressure = 0  # negative pressure is not turning mental strength around

                try:
                    pressure_factor = self.pressure_factors[player][int(total_pressure)] ** signum  # convert pressure to factor
                except IndexError:
                    # if pressure is higher than maximum pressure assigned, take the extreme one
                    pressure_factor = self.pressure_factors[player][-1] ** signum

            else:
                pressure_factor = 1

            pressure_factor *= vol_fac  # multiply with current volatility factor

            # what the bot aims at
            if aim_field == "T":
                random_rad = np.random.normal(loc=outshots.board_mean_fields["T"], scale=self.scales_rad[player]["T"]*pressure_factor)
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num], scale=self.scales_azi[player]["T"]*pressure_factor)
            elif aim_field == "S":
                random_rad = np.random.normal(loc=outshots.board_mean_fields["S"], scale=self.scales_rad[player]["S"]*pressure_factor)
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num], scale=self.scales_azi[player]["S"]*pressure_factor)
            elif aim_field == "D":
                random_rad = np.random.normal(loc=outshots.board_mean_fields["D"], scale=self.scales_rad[player]["D"]*pressure_factor)
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num], scale=self.scales_azi[player]["D"]*pressure_factor)
            elif aim_field == "B":  # rad B must be positive (inversion lateron!)
                random_rad = abs(np.random.normal(loc=outshots.board_mean_fields[aim],
                                                  scale=self.scales_rad[player]["B"]*pressure_factor))
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num],  # substitute angles by distances
                                              scale=self.scales_azi[player]["B"]*pressure_factor)

            bot_hits[0].append(random_rad)
            bot_hits[1].append(random_azi)

            ## Check for geometry problems
            if random_rad < 0:  # below bulls eye
                random_rad = abs(random_rad)
                random_azi -= 18000  # revert azimuth (correction for <0 follows below)

            if random_azi > 36000:  # correction of azimuth for <0° or >360°
                random_azi -= 36000
            elif random_azi < 0:
                random_azi += 36000

            if botcnt > 0 and self.m.ml.settings_dict['botrewind'][1] == -1:  # Rewind and use previous throws
                random_azi = self.m.ml.BOT_hits[player][-botcnt][k][0]
                random_rad = self.m.ml.BOT_hits[player][-botcnt][k][1]
            else:
                if k == 0:
                    self.m.ml.BOT_hits[player].append([])
                self.m.ml.BOT_hits[player][-1].append([random_azi, random_rad])  # Store Bot throws in case of rewind

            if random_rad > 17000:
                if (aim_field == "D" and score == aim_num * 2) or (aim_field == "B50" and score == 50):
                    self.attempts += 1  # Checkout attempt with no score
                self.m.pr("  0 (miss)")
                continue

            ## what the bot actually hit
            # Field
            hit_str = ""
            for field in outshots.board_pos_fields:  # browse through all possible fields
                if field == "S":  # two fields for S (inner & outer) -> individual solution
                    if (outshots.board_pos_fields["S"][0] < random_rad < outshots.board_pos_fields["S"][1]) \
                            or (outshots.board_pos_fields["S"][2] < random_rad < outshots.board_pos_fields["S"][3]):
                        hit_str += "S"
                        break
                else:  # all other fields
                    if outshots.board_pos_fields[field][0] < random_rad < outshots.board_pos_fields[field][1]:
                        hit_str += field[0]
                        break

            # Number
            for number in outshots.board_pos_nums:  # browse through all possible fields
                if field[0] == "B":
                    if random_rad > outshots.board_pos_fields["B50"][1]:
                        hit_str += "25"
                        number = 25
                        break
                    else:
                        hit_str += "50"
                        number = 50
                        break
                else:
                    if outshots.board_pos_nums[number][0] < random_azi < outshots.board_pos_nums[number][1]:
                        hit_str += str(number)
                        break

            if (aim_field == "D" and score == aim_num * 2) or (aim_field == "B50" and score == 50):
                self.attempts += 1

            # Calculate actual result of throw
            factor = outshots.field_factors[field[0]]
            bot_throw = factor * number
            total_botscore += bot_throw
            self.m.pr("{:3d} ({})".format(bot_throw, field[0] + str(number)))
            score -= bot_throw

            if score == 0:
                if hit_str == aim:
                    self.attempts -= 1  # successfull co will be added in stats later
                    self.checkout(ndarts=abs(ndarts-3))
                    if botcnt > 0:
                        self.m.ml.bot_rewind_count[player] -= 1
                    if self.m.ml.settings_dict['visualize'][1] == 1:
                        boardplot = vcd.Board_plot(rad=bot_hits[0], azi=bot_hits[1])
                        boardplot.new_plot()
                    return "checkout"

            if score <= 1:
                self.m.pr("\txx Score Busted! xx")
                total_botscore = 0
                break

        if botcnt > 0:
            self.m.ml.bot_rewind_count[player] -= 1
        self.m.pr("\t   SUM : {:3d}".format(total_botscore))
        self.scores[player] -= total_botscore
        self.statistics(player=player, score=total_botscore, ndarts=3)
        self.m.pr(self.player_string + str(self.scores[player]))
        self.toggle_player()
        self.make_image()  # Make Image at the end of bot's throw
        if self.m.ml.settings_dict['visualize'][1] == 1:
            boardplot = vcd.Board_plot(rad=bot_hits[0], azi=bot_hits[1])
            boardplot.new_plot()

    def checkout(self, ndarts=1):
        ndarts_total = self.m.ml.stats_dict[self.current_player]['Dtot'][1] + ndarts
        mode = "c" + str(ndarts)
        self.scoring(player=self.current_player, score=self.scores[self.current_player], mode=mode)
        self.m.pr("\t{} won with {:d} darts!".format(self.m.ml.players_dict[self.current_player][0],
                                                     ndarts_total))

    def scoring(self, player, score, mode=None):
        self.m.ml.REWIND_STORE_list = []  # delete all entries in rewind list
        score_visit = None
        ndarts = 3
        if mode == 'set':
            score_visit = self.scores[player] - score
            self.scores[player] = score

        elif mode == 'half':
            score_visit = self.scores[player] // 2
            self.scores[player] //= 2

        elif mode == "regular":
            score_visit = score
            if self.scores[player] - score_visit <= 1:  # score busted
                score_visit = 0
            else:
                self.scores[player] -= score_visit

        elif mode.startswith("c"):
            self.statistics(player=player, score=score, ndarts=int(mode[1]), co='yes')
            self.m.pr(self.player_string + str(0))
            self.scores[player] = 0
            return

        self.statistics(player=player, score=score_visit, ndarts=ndarts)
        self.m.pr(self.player_string + str(self.scores[player]))
        self.toggle_player()
        self.make_image()  # Make Image at the end of the player's throw

    def toggle_player(self):
        self.current_player = (self.current_player + 1) % self.m.ml.nplayers

    def statistics(self, player, score, ndarts=3, co=None):
        for i in [1, 2, 3, 4]:
            self.m.ml.stats_dict[player]['Dtot'][i] += ndarts
            self.m.ml.stats_dict[player]['CoAtt'][i] += self.attempts
            if co:
                self.m.ml.stats_dict[player]['CoAtt'][i] += 1  # successfull checkout = another attempt
                self.m.ml.stats_dict[player]['CoSucc'][i] += 1
                if score > 100:
                    self.m.ml.stats_dict[player]['T+Out'][i] += 1
                if self.m.ml.stats_dict[player]['CoSucc'][i] == 1:  # first checkout on this level
                    self.m.ml.stats_dict[player]['AvgCo'][i] = score
                else:
                    self.m.ml.stats_dict[player]['AvgCo'][i] = (self.m.ml.stats_dict[player]['AvgCo'][i] *
                                                                (self.m.ml.stats_dict[player]['CoSucc'][i] - 1)
                                                                + score) / self.m.ml.stats_dict[player]['CoSucc'][i]

            try:
                self.m.ml.stats_dict[player]['CoRat'][i] = self.m.ml.stats_dict[player]['CoSucc'][i]*100 \
                                                           / self.m.ml.stats_dict[player]['CoAtt'][i]
            except ZeroDivisionError:
                self.m.ml.stats_dict[player]['CoRat'][i] = 0.0
            if i == 4:
                self.m.ml.stats_dict[player]['Avg'][4] = (((self.m.ml.stats_dict[player]['Dtot'][4] *
                                                            self.m.ml.stats_dict[player]['Avg'][4]) +
                                                           (self.m.ml.stats_dict[player]['Dtot'][3] *
                                                            self.m.ml.stats_dict[player]['Avg'][3])) /
                                                          (self.m.ml.stats_dict[player]['Dtot'][3] +
                                                           self.m.ml.stats_dict[player]['Dtot'][4]))
            else:
                self.m.ml.player_scores[player][i-1].append(score)
                self.m.ml.stats_dict[player]['Avg'][i] = (np.sum(self.m.ml.player_scores[player][i-1])
                                                          / self.m.ml.stats_dict[player]['Dtot'][i]) * 3

            if score == 180:
                self.m.ml.stats_dict[player]['S180'][i] += 1
            elif score >= 160:
                self.m.ml.stats_dict[player]['S160+'][i] += 1
            elif score >= 140:
                self.m.ml.stats_dict[player]['S140+'][i] += 1
            elif score >= 100:
                self.m.ml.stats_dict[player]['S100+'][i] += 1

            if score > self.m.ml.stats_dict[player]['HiScore'][i]:
                self.hiscore_evolution[player][i-1].append(score)  # new highscore on level, add to highscore_list
                self.m.ml.stats_dict[player]['HiScore'][i] = score
            else:  # no new highscore on level, repeat last value
                self.hiscore_evolution[player][i-1].append(self.hiscore_evolution[player][i-1][-1])

        # Printing the current stats
        if self.m.ml.settings_dict['legavg'][1] == 1:
            print("\tAverage - leg ({}): {:5.2f}".format(self.m.ml.players_dict[player][0],
                                                         round(self.m.ml.stats_dict[player]['Avg'][1], 2)))
        if self.m.ml.settings_dict['matchavg'][1] == 1:
            print("\tAverage - match ({}): {:5.2f}".format(self.m.ml.players_dict[player][0],
                                                           round(self.m.ml.stats_dict[player]['Avg'][3], 2)))
        if self.m.ml.settings_dict['ndarts'][1] == 1:
            print("\tNumber of Darts - leg ({}): {:d}".format(self.m.ml.players_dict[player][0],
                                                              self.m.ml.stats_dict[player]['Dtot'][1]))

        if co:  # we have a checkout - clean up
            self.m.ml.wins[player][0] += 1  # legs total
            self.m.ml.wins[player][1] += 1  # legs in this set
            all_wins = sorted(self.m.ml.wins[pl][1] for pl in range(self.m.ml.nplayers))[::-1]
            try:
                lead = all_wins[0] - all_wins[1]  # new leading distance between leading player and follower
            except IndexError:  # One Player
                lead = -1
            if self.m.ml.nplayers == 2 and (lead == (self.m.ml.nlegs - self.m.ml.leg) or
                                            self.m.ml.leg + 1 == self.m.ml.nlegs) \
                    or self.m.ml.nplayers != 2 and any(self.m.ml.wins[pl][1] == self.m.ml.nlegs for pl in range(self.m.ml.nplayers)):
                where = [1, 2]  # set is finished, clean set too
                vict_player = np.argmax([i[1] for i in self.m.ml.wins])  # find out who won the set (only needed for nplayers > 2)
                self.m.ml.wins[vict_player][2] += 1
                if any(self.m.ml.wins[pl][2] == self.m.ml.nsets for pl in range(self.m.ml.nplayers)):
                    self.m.ml.final_results = self.print_stats(which=3)

                for i in range(self.m.ml.nplayers):
                    self.m.ml.wins[i][1] = 0  # reset legs in this set
                self.m.ml.set_results = self.print_stats(which=2, matchscore=False)
            else:
                where = [1]  # leg is finished, clean only leg

            for pl in range(self.m.ml.nplayers):  # nplayers
                for w in where:
                    self.m.ml.player_scores[pl][w-1] = list()
                    for key in self.m.ml.stats_dict[player]:
                        self.m.ml.stats_dict[pl][key][w] = 0

    def print_matchscore(self):
        print_str = "++++\n"
        print_str += "\tMatch Score ({}".format(self.m.ml.players_dict[0][0])

        for pl_num in range(1, self.m.ml.nplayers):
            print_str += " vs. {}".format(self.m.ml.players_dict[pl_num][0])
        print_str += "):\n"

        if self.m.ml.nsets > 1:
            print_str += "\t\tSets: {:d}".format(self.m.ml.wins[0][2])
            for pl_num in range(1, self.m.ml.nplayers):
                print_str += " - {:d}".format(self.m.ml.wins[pl_num][2])
            print_str += "\n"

        print_str += "\t\tLegs: {:d}".format(self.m.ml.wins[0][1])
        for pl_num in range(1, self.m.ml.nplayers):
            print_str += " - {:d}".format(self.m.ml.wins[pl_num][1])
        print_str += "\n"
        print_str += "++++\n"
        return print_str

    def print_stats(self, which=None, who=None, matchscore=True):
        if matchscore:
            print_string = self.print_matchscore()
        else:
            print_string = ""
        if not who:
            who = list(range(self.m.ml.nplayers))
        else:
            who = [who-1]

        if not which:
            which = [1, 2, 3]
        else:
            which = [which]

        labels = ['dummy', 'leg', 'set', 'match']
        for player in who:
            print_string += "++++\n" 
            print_string += "\tStatistics for player %i (%s)\n" % (player + 1, self.m.ml.players_dict[player][0])
            for level in which:
                print_string += "\t++\n"
                print_string += "\t\tAverage (%s): %6.2f\n" % (labels[level],
                                                               self.m.ml.stats_dict[player]['Avg'][level])
                print_string += "\t\tScore 100+ (%s): %i\n" % (labels[level],
                                                               self.m.ml.stats_dict[player]['S100+'][level])
                print_string += "\t\tScore 140+ (%s): %i\n" % (labels[level],
                                                               self.m.ml.stats_dict[player]['S140+'][level])
                print_string += "\t\tScore 160+ (%s): %i\n" % (labels[level],
                                                               self.m.ml.stats_dict[player]['S160+'][level])
                print_string += "\t\tScore 180s (%s): %i\n" % (labels[level],
                                                               self.m.ml.stats_dict[player]['S180'][level])
                print_string += "\t\tHighest Score (%s): %i\n" % (labels[level],
                                                                  self.m.ml.stats_dict[player]['HiScore'][level])
                print_string += "\t\tCheckout Attempts (%s): %i\n" % (labels[level],
                                                                      self.m.ml.stats_dict[player]['CoAtt'][level])
                print_string += "\t\tCheckouts Successfull (%s): %i\n" % (labels[level],
                                                                          self.m.ml.stats_dict[player]['CoSucc'][level])
                print_string += "\t\tCheckout Rate (%s): %6.2f\n" % (labels[level],
                                                                     self.m.ml.stats_dict[player]['CoRat'][level])
        print_string += "++++"
        return print_string

    def all_suggestions(self, score, ndarts):
        self.m.pr("++++")
        self.m.pr("\tSuggested shots for player {:d} ({}) with {:d} darts in hand at score {:d}:".
                  format(self.current_player + 1, self.m.ml.players_dict[self.current_player][0],
                         ndarts, score))

        if ndarts == 3:
            score_lvl3 = score
            if score_lvl3 > 230:
                all_lvl3 = ["T20"]
            else:
                all_lvl3 = self.outshot_dict[0][score_lvl3]
            for lvl3 in all_lvl3:
                score_lvl2 = score_lvl3 - score_from_field(lvl3)
                if score_lvl2 > 230:
                    all_lvl2 = ["T20"]
                elif score_lvl2 == 0:
                    self.m.pr("\t({})".format(lvl3))
                    continue
                else:
                    all_lvl2 = self.outshot_dict[1][score_lvl2]
                for lvl2 in all_lvl2:
                    score_lvl1 = score_lvl2 - score_from_field(lvl2)
                    if score_lvl1 > 230:
                        all_lvl1 = ["T20"]
                    elif score_lvl1 == 0:
                        self.m.pr("\t({} {})".format(lvl3, lvl2))
                        continue
                    else:
                        all_lvl1 = self.outshot_dict[2][score_lvl1]
                    for lvl1 in all_lvl1:
                        self.m.pr("\t({} {} {})".format(lvl3, lvl2, lvl1))

        elif ndarts == 2:
            score_lvl2 = score
            if score_lvl2 > 230:
                all_lvl2 = ["T20"]
            else:
                all_lvl2 = self.outshot_dict[1][score_lvl2]
            for lvl2 in all_lvl2:
                score_lvl1 = score_lvl2 - score_from_field(lvl2)
                if score_lvl1 > 230:
                    all_lvl1 = ["T20"]
                elif score_lvl1 == 0:
                    self.m.pr("\t({})".format(lvl2))
                    continue
                else:
                    all_lvl1 = self.outshot_dict[2][score_lvl1]
                for lvl1 in all_lvl1:
                    self.m.pr("\t({} {})".format(lvl2, lvl1))

        elif ndarts == 1:
            score_lvl1 = score
            if score_lvl1 > 230:
                all_lvl1 = ["T20"]
            else:
                all_lvl1 = self.outshot_dict[2][score_lvl1]
            for lvl1 in all_lvl1:
                self.m.pr("\t({})".format(lvl1))
        self.m.pr("++++")

    def suggestion(self, score):
        if not self.m.ml.settings_dict['suggest'][1] == 1:
            return ""
        if score > 170:
            return "(T20 T20 T20)"
        suggest_str = "("
        for i in range(3):
            aim = self.outshot_dict[i][score][0]
            field = aim[0]
            number = int(aim[1:])
            factor = outshots.field_factors[field[0]]
            score_value = factor * number
            suggest_str += aim + " "
            score -= score_value
            if score == 0:
                return suggest_str[:-1] + ")"
        return (suggest_str[:-1]) + ")"


class MainLoop:
    def __init__(self, main):
        self.m = main
        self.autoplay = False
        self.skills_dict = None
        self.save_slots = []

    def reset(self, mode='all'):
        # Achtung beim Reset der Player_stats -> zu dem Zeitpunkt muss die Zahl der Player bekannt sein
        self.stats_dict = []
        self.STORE_list = []
        self.REWIND_STORE_list = []
        self.BOT_hits = [[]]
        self.bot_rewind_count = []
        if mode == 'all':  # this is skipped for autoplay
            self.players = list()
            self.nplayers_available = None
            self.players_dict = None
            self.whos_a_bot = []
            self.whos_a_human = []
            self.settings_dict = None

        self.final_results = None
        self.set_results = None

    def reset_player_stats(self):
        player_stats = {'Avg': [['Avg', 'fl'], 0, 0, 0, 0],
                        'Dtot': [['Darts in total', 'int'], 0, 0, 0, 0],
                        'CoAtt': [['Checkout - attempts', 'int'], 0, 0, 0, 0],
                        'CoSucc': [['Checkout - successfull', 'int'], 0, 0, 0, 0],
                        'CoRat': [['Checkout - percentage', 'fl'], 0, 0, 0, 0],
                        'S100+': [['Score 100+', 'int'], 0, 0, 0, 0],
                        'S140+': [['Score 140+', 'int'], 0, 0, 0, 0],
                        'S160+': [['Score 160+', 'int'], 0, 0, 0, 0],
                        'S180': [['Score 180+', 'int'], 0, 0, 0, 0],
                        'T+Out': [['Outshots 100+', 'int'], 0, 0, 0, 0],
                        'HiScore': [['Highest Score', 'int'], 0, 0, 0, 0],
                        'HiCo': [['Highest Checkout', 'int'], 0, 0, 0, 0],
                        'AvgCo': [['Average Checkout', 'fl'], 0, 0, 0, 0]}
        self.stats_dict = [deepcopy(player_stats) for _ in range(self.nplayers)]  # nplayers

    def global_statistics(self):
        self.read_players()
        self.m.pr("List of players:")
        for i in range(self.nplayers_available):
            self.m.pr("{:d}: {}".format(i+1, os.path.splitext(self.players[i])[0]))
        self.m.pr("-1: **Back to main menu**")
        player = self.check_input("choose Player (#) >>> ", -1, self.nplayers_available)
        if player == -1:
            return
        self.open_players(p=[self.players[player]])

        self.m.pr("\n\n#### STATISTICS ####\n")
        self.m.pr("Name of Player: {}".format(self.players_dict[0][0]))
        if self.players_dict[0][1] == "1":
            pl_type = "Human Player"
        elif self.players_dict[0][1] in ["2", "3"]:
            pl_type = "Computer Player"
        else:
            pl_type = "Unknown player type"
        self.m.pr("Player type: {}".format(pl_type))
        if pl_type == "Computer Player":
            if self.players_dict[0][1] == "2":
                bot_type = "Simple Bot"
            elif self.players_dict[0][1] == "3":
                bot_type = "Complex Bot"
            else:
                bot_type = "Unknown Bot type"
            self.m.pr("Bot type: {}".format(bot_type))
            skillz = [int(element) for element in self.players_dict[0][2].split(',')]
            if bot_type == "Simple Bot":
                skill = skillz[0]
                self.m.pr("Skill level (1-50): {:d}".format(skill))
            else:
                self.m.pr("Skill level for vertical precision (distance to bull) (1 to 50): {:d}"
                          .format(skillz[0]))
                self.m.pr("Skill level for azimuthal precision (angle to the sides) (1 to 50): {:d}"
                          .format(skillz[1]))
                if skillz[2] == 1:
                    bot_special = "None"
                elif skillz[2] == 2:
                    bot_special = "Scoring"
                elif skillz[2] == 3:
                    bot_special = "Checkouts"
                else:
                    bot_special = "Unknown"
                self.m.pr("Bot speciality: {}".format(bot_special))
                if skillz[2] > 1:
                    self.m.pr("Speciality skills (1 to 5): {:d}".format(skillz[3]))
                self.m.pr("Mental strength (-25 to +25): {:d}".format(skillz[4]))
                self.m.pr("Experience / Experimentation (1 to 50): {:d}".format(skillz[5]))

        self.m.pr("\nTotal Average: {:5.2f}".format(self.stats_dict[0]['Avg'][-1]))
        self.m.pr("Darts in total: {:d}".format(self.stats_dict[0]['Dtot'][-1]))
        self.m.pr("Checkouts - attempts: {:d}".format(self.stats_dict[0]['CoAtt'][-1]))
        self.m.pr("Checkouts - successful: {:d}".format(self.stats_dict[0]['CoSucc'][-1]))
        self.m.pr("Checkouts - rate: {:4.2f} %".format(self.stats_dict[0]['CoRat'][-1]))
        self.m.pr("Scores 100+: {:d}".format(self.stats_dict[0]['S100+'][-1]))
        self.m.pr("Scores 140+: {:d}".format(self.stats_dict[0]['S140+'][-1]))
        self.m.pr("Scores 160+: {:d}".format(self.stats_dict[0]['S160+'][-1]))
        self.m.pr("Scores 180: {:d}".format(self.stats_dict[0]['S180'][-1]))
        self.m.pr("Tons Out (100+): {:d}".format(self.stats_dict[0]['T+Out'][-1]))
        self.m.pr("Highest Score ever: {:d}".format(self.stats_dict[0]['HiScore'][-1]))
        self.m.pr("Highest Checkout ever: {:d}".format(self.stats_dict[0]['HiCo'][-1]))
        self.m.pr("Average Checkout: {:4.2f}\n\n".format(self.stats_dict[0]['AvgCo'][-1]))
        self.reset()
        return

    def new_game(self):
        self.read_settings()
        self.read_players()
        self.nplayers = self.check_input("How many players for new match? (1-10) >>> ", -1, 10, True)

        self.m.pr("List of players:")
        for i in range(self.nplayers_available):
            self.m.pr("{:d}: {}".format(i+1, os.path.splitext(self.players[i])[0]))
        self.m.pr("-1: **Back to main menu**")
        players = []
        while len(players) < self.nplayers:
            player = self.check_input("Choose Player {:d}(#) >>> ".format(len(players)+1), -1, self.nplayers_available)
            if player == -1:
                return
            if player-1 in players:
                self.m.pr("\t# Player {:d} ({}) is already selected for this match".format(player, os.path.splitext(self.players[player-1])[0]))
                continue
            else:
                players.append(player-1)

        self.open_players(p=[self.players[player] for player in players])
        self.m.pr("***\n1: 101\n2: 201\n3: 301\n4: 401\n5: 501\n6: 601\n7: 701\n8: 801\n9: 901\n-1: **Back to main menu**")
        x01 = self.check_input("X01(#) >>> ", -1, 9)
        if x01 == -1:
            return
        self.x01 = x01*100 + 1

        self.nsets = self.check_input("***\nNumber of sets (first to) >>> ", -1, 1000)
        if self.nsets == -1:
            return
        while True:
            if self.nplayers == 2:
                self.nlegs_condition = "best of"
            else:
                self.nlegs_condition = "first to"
            self.nlegs = self.check_input("***\nNumber of legs ({}) >>> ".format(self.nlegs_condition), -1, 1001)
            if self.nlegs == -1:
                return
            if self.nsets > 1 and self.nplayers == 2 and self.nlegs % 2 == 0:
                self.m.pr("Number of legs needs to be uneven number if more than 1 set is played!")
            else:
                break

        # initialize lists
        self.player_scores = [[[], [], []] for _ in range(self.nplayers)]  # three empty lists per player
        self.wins = [[0, 0, 0] for _ in range(self.nplayers)]  # wins[player][legs_total, legs, sets]
        self.set = 0
        self.loop_game()

    def load_new_game(self, slot):
        self.read_settings()
        load_obj = load_object(load_file=self.save_slots[slot-1])
        self.STORE_list = load_obj[:-1]   # Rewind läuft beim ersten Mal ins Leere - wird evtl zusätzlich was abgespeichert?

        scores, current_player, hiscore_evolution, pl_dict_unneeded, self.stats_dict, self.x01, self.nsets, \
            self.nlegs, self.player_scores, self.wins, self.legs_needed, self.active_players, self_corr_vol, \
            self.BOT_hits = load_obj[-1]

        self.nplayers = len(self.active_players)
        self.open_players(p=self.active_players)
        load_paras = scores, current_player, hiscore_evolution, self_corr_vol
        self.set = sum(self.wins[i][2] for i in range(self.nplayers))
        self.loop_game(load_paras)

    def loop_game(self, load_paras=None):
        while not any(self.wins[i][2] == self.nsets for i in range(self.nplayers)):
            if self.nplayers == 2:
                self.legs_needed = (self.nlegs // 2) + 1
            else:
                self.legs_needed = self.nlegs
            self.leg = 0
            while self.eval_multiplayer():  # catch draws for nplayers == 2
                self.sets_won_before = sum(self.wins[i][2] for i in range(self.nplayers))
                self.m.new_game(load_paras)
                load_paras = None  # override load_paras, from here on play the regular game
                if self.settings_dict['savstats'][1] == 1:
                    self.save_stats()
                if not sum(self.wins[i][2] for i in range(self.nplayers)) == self.sets_won_before:  # if sum of sets won changed, then break, else increase legs
                    break
                self.leg += 1

            if not self.nsets == 1:
                self.m.pr(self.set_results)
            self.set += 1

        # Game finished:
        if not self.autoplay:
            self.m.pr(self.final_results)
            self.save_stats()

    def eval_multiplayer(self):
        if self.nplayers == 2:
            condition = self.leg < self.nlegs  # best of X legs
        else:
            condition = True  # first to X legs (no condition needed, no draw allowed)
        return condition

    def init_autoplay(self, name, skills, bot_type):
        bot_type = str(bot_type+1)
        skills = ",".join(str(item) for item in skills)
        self.autoplay = True
        self.read_settings()
        for key in self.settings_dict:
            self.settings_dict[key][1] = -1
        self.players_dict = {0: [name, bot_type, skills],
                             1: [name, bot_type, skills]}
        # self.players_dict = {0: ["", "3", "20, 16, 3, 2, 8, 18"],
        #                      1: ["", "3", "20, 16, 3, 2, 8, 18"]}
        self.stats_dict = {0: {'Avg': [['Avg', 'fl'], 0, 0, 0, 0.0],
                               'Dtot': [['Darts in total', 'int'], 0, 0, 0, 0],
                               'CoAtt': [['Checkout - attempts', 'int'], 0, 0, 0, 0],
                               'CoSucc': [['Checkout - successfull', 'int'], 0, 0, 0, 0],
                               'CoRat': [['Checkout - percentage', 'fl'], 0, 0, 0, 0.0],
                               'S100+': [['Score 100+', 'int'], 0, 0, 0, 0],
                               'S140+': [['Score 140+', 'int'], 0, 0, 0, 0],
                               'S160+': [['Score 160+', 'int'], 0, 0, 0, 0],
                               'S180': [['Score 180+', 'int'], 0, 0, 0, 0],
                               'T+Out': [['Outshots 100+', 'int'], 0, 0, 0, 0],
                               'HiScore': [['Highest Score', 'int'], 0, 0, 0, 120],
                               'HiCo': [['Highest Checkout', 'int'], 0, 0, 0, 0],
                               'AvgCo': [['Average Checkout', 'fl'], 0, 0, 0, 0.0]},
                           1: {'Avg': [['Avg', 'fl'], 0, 0, 0, 0.0],
                               'Dtot': [['Darts in total', 'int'], 0, 0, 0, 0],
                               'CoAtt': [['Checkout - attempts', 'int'], 0, 0, 0, 0],
                               'CoSucc': [['Checkout - successfull', 'int'], 0, 0, 0, 0],
                               'CoRat': [['Checkout - percentage', 'fl'], 0, 0, 0, 0.0],
                               'S100+': [['Score 100+', 'int'], 0, 0, 0, 0],
                               'S140+': [['Score 140+', 'int'], 0, 0, 0, 0],
                               'S160+': [['Score 160+', 'int'], 0, 0, 0, 0],
                               'S180': [['Score 180+', 'int'], 0, 0, 0, 0],
                               'T+Out': [['Outshots 100+', 'int'], 0, 0, 0, 0],
                               'HiScore': [['Highest Score', 'int'], 0, 0, 0, 120],
                               'HiCo': [['Highest Checkout', 'int'], 0, 0, 0, 0],
                               'AvgCo': [['Average Checkout', 'fl'], 0, 0, 0, 0.0]}}
        self.x01 = 501
        self.nsets = 1
        self.nlegs = 30
        avg_auto = list()
        corat_auto = list()
        avgco_auto = list()
        for i_match in range(20):
            # initialize lists
            self.player_scores = [[[], [], []], [[], [], []]]
            self.wins = [[0, 0, 0], [0, 0, 0]]  # wins[player][legs_total, legs, sets]
            self.set = 0
            self.loop_game()
            sys.stdout.write("\rEvaluating ... {:d}%".format((i_match+1)*5))
            sys.stdout.flush()
            avg_auto.append(self.m.ml.stats_dict[0]['Avg'][3])
            corat_auto.append(self.m.ml.stats_dict[0]['CoRat'][3])
            avgco_auto.append(self.m.ml.stats_dict[0]['AvgCo'][3])
            self.reset(mode='soft')  # soft reset skips player and settings reset (but resets statistics)
        self.autoplay = False
        self.m.pr("\n# Bot's Average: {:5.2f}\n# Bot's Checkout-rate: {:4.2f}\n# Bot's Average Checkout: {:5.2f}\n##"
                  .format(np.mean(np.asarray(avg_auto)), np.mean(np.asarray(corat_auto)), np.mean(np.asarray(avgco_auto))))

    def user_input(self):
        while True:
            self.reset()
            self.read_settings()
            self.m.pr("***\n1: new game\n2: load savegame\n3: new player\n4: statistics\n5: settings\n-1: exit")
            user_in = self.check_input(">>> ", -1, 6)

            if user_in == 1:
                self.new_game()
            if user_in == 2:
                answer = self.load_savegame()
                if not answer:
                    continue
                else:
                    self.load_new_game(answer)
            if user_in == 3:
                self.new_player()
            if user_in == 4:
                self.global_statistics()
            if user_in == 5:
                self.settings()
            if user_in == -1:
                exit()

    def settings(self):
        onoff = {-1: "off", 1: "on"}
        while True:
            self.m.pr("\n~~~~ SETTINGS ~~~~\n")
            keykey = list()
            for i, key in enumerate(self.settings_dict):
                keykey.append(key)
                self.m.pr("{:d}: {} - {}".format(i+1, self.settings_dict[key][0], onoff[self.settings_dict[key][1]]))
            self.m.pr("-1: Return")
            settings_input = self.check_input("Toggle On/Off [#] >>> ", -1, len(self.settings_dict))
            if settings_input == -1:
                self.save_settings()
                return
            settings_input -= 1

            key = keykey[settings_input]
            self.settings_dict[key][1] *= -1  # toggle Setting
            self.save_settings()

    def save_settings(self):
        with open(path+"/Settings.dat", 'w') as settings_file:
            for key in self.settings_dict:
                save_string = "%s=%s=%i\n" % (key, self.settings_dict[key][0], self.settings_dict[key][1])
                settings_file.write(save_string)

    def read_settings(self):
        if not os.path.isfile(path+"/Settings.dat"):
            content = list()
            content.append("ndarts=Always show number of darts in current leg=-1\n")
            content.append("legavg=Always show leg average=-1\n")
            content.append("psychmod=Bot's realistic psychology module=1\n")
            content.append("botrewind=Bot places new throw after rewind=-1\n")
            content.append("matchavg=Always show match average=1\n")
            content.append("suggest=Always show suggested scores for visit=1\n")
            content.append("bottime=Delay bots throw (750ms)=1\n")
            content.append("visualize=Visualize bot throw=1\n")
            content.append("savstats=Save statistics for players after each leg=1\n")
            content.append("logging=Always save match-log=-1\n")
            with open(path+"/Settings.dat", 'w') as settings_file:
                settings_file.writelines(content)
        else:
            with open(path+"/Settings.dat", 'r') as settings_file:
                content = settings_file.readlines()

        content = [item.rstrip() for item in content]
        settings_parameter, settings_label_val = (list(), list())
        for item in content:
            settings_parameter.append(item.split('=')[0])
            settings_label_val.append([item.split('=')[1], int(item.split('=')[2])])
        self.settings_dict = dict(zip(settings_parameter, settings_label_val))

    def read_savegames(self, print_slots=True):
        dir_sg = os.listdir(path=path)
        self.save_slots = list()
        for file in dir_sg:
            if file.endswith(".sav"):
                self.save_slots.append(file)
        self.nslots = len(self.save_slots)
        self.save_slots = sorted(self.save_slots)

        if print_slots:
            self.m.pr("List of saved matches:")
            for i in range(self.nslots):
                load_str = ""
                sav_str = os.path.splitext(self.save_slots[i])[0]
                stamp_str = sav_str.split("#")[0]
                date_str = stamp_str.split("_")[0]
                yyyy = date_str[:4]
                mm = date_str[4:6]
                dd = date_str[6:]
                time_str = stamp_str.split("_")[1]
                hh = time_str.split("-")[0]
                minu = time_str.split("-")[1]
                sec = time_str.split("-")[2]

                load_obj = load_object(load_file=self.save_slots[i])
                _, _, _, player_dict, _, _, nsets, nlegs, _, wins, legs_needed, _, _, _ = load_obj[-1]
                players = [player_dict[i][0] for i in range(len(player_dict))]
                nplayers = len(players)
                legs_won = [wins[i][1] for i in range(nplayers)]
                sets_won = [wins[i][2] for i in range(nplayers)]
                if nplayers == 2:
                    leg_mode = "best of"
                else:
                    leg_mode = "first to"

                load_str += "\t{:02d}: {}-{}-{} {}:{}:{}".format(i + 1, yyyy, mm, dd, hh, minu, sec)
                player_str = " ... {}".format(players[0])
                sets_str = ": {}".format(sets_won[0])
                legs_str = " sets (first to {:d}) & {:d}".format(nsets, legs_won[0])
                for pl in range(1, nplayers):
                    player_str += " vs. {}".format(players[pl])
                    sets_str += "-{:d}".format(sets_won[pl])
                    legs_str += "-{:d}".format(legs_won[pl])

                load_str += player_str + sets_str + legs_str + " legs ({} {:d})".format(leg_mode, legs_needed)
                self.m.pr(load_str)
            self.m.pr("\t -1: return")

    def load_savegame(self):
        self.read_savegames()
        user_in = self.check_input("Load match >>> ", -1, self.nslots)
        if user_in == -1:
            return
        return user_in

    def read_players(self):
        dir_pl = os.listdir(path=path)
        for file in dir_pl:
            if file.endswith(".drt"):
                self.players.append(file)
        self.nplayers_available = len(self.players)

    def open_players(self, p):
        self.reset_player_stats()  # create empty self.stats_dict
        n_p = len(p)
        self.active_players = p
        pl_content = [list() for _ in range(n_p)]  # n Players for new match, 1 Player for view_stats
        for pl in range(n_p):
            with open(path+"/"+p[pl], "r") as file:
                pl_content[pl].append(file.readline().rstrip().split('=')[1])
                pl_content[pl].append(file.readline().rstrip().split('=')[1])
                pl_content[pl].append(file.readline().rstrip().split('=')[1])
                stat_content = file.readlines()
            self.stat_keys = [item.rstrip().split('=')[0] for item in stat_content]
            stat_values = [item.rstrip().split('=')[1] for item in stat_content]
            for i, key in enumerate(self.stat_keys):
                if self.stats_dict[pl][key][0][1] == 'int':
                    self.stats_dict[pl][key][4] = int(stat_values[i])
                elif self.stats_dict[pl][key][0][1] == 'fl':
                    self.stats_dict[pl][key][4] = float(stat_values[i])
        self.players_dict = dict(zip([i for i in range(n_p)], pl_content))

        for pl in range(n_p):
            if int(self.players_dict[pl][1]) > 1:
                self.whos_a_bot.append(pl)
        self.whos_a_bot_straight = list(range(len(self.whos_a_bot)))  # e.g. [0,1] for whos_a_bot [1,4]
        self.whos_a_human = [i for i in range(self.nplayers) if i not in self.whos_a_bot]
        self.BOT_hits = [[] for _ in range(self.nplayers)]  # don't care about empty lists for humans, it's easier later
        self.bot_rewind_count = [0 for _ in range(self.nplayers)]  # same as above

    def save_stats(self):
        for player in range(self.nplayers):
            with open(path+"/"+self.players_dict[player][0]+'.drt', 'w') as file:
                file.write("name=%s\n" % self.players_dict[player][0])
                file.write("type=%s\n" % str(self.players_dict[player][1]))
                file.write("skill=%s\n" % self.players_dict[player][2])
                for i, key in enumerate(self.stats_dict[player]):
                    file.write("%s=%s\n" % (key, str(self.stats_dict[player][key][4])))

    def new_player(self):
        name = input("Name of Player\n>>> ")
        player_type = self.check_input("1: Human Player; 2: Computer Player; -1: Return\n>>> ", -1, 2)
        if player_type == -1:
            return
        skill_level = [-1, -1, -1, -1, -1, -1]
        if player_type == 2:
            bot_type = self.check_input("\t1: Simple Bot (skill level X); 2: Complex Bot (specify all skills)\n\t>>> ", -1, 2)
            if bot_type == -1:
                return
            if bot_type == 1:
                skill_level = self.check_input("\tSkill level (1-50)\n>>> ", -1, 50)
                if skill_level == -1:
                    return
                skill_level = [skill_level for _ in range(2)]  # vprec + hprec
                skill_level.append(1)  # Bot speciality = None
                skill_level.append(1)  # Speciality skills = 1
                skill_level.append(0)  # Mental strength = 0
                skill_level.append(10)  # Experimentation = 10
            else:
                skill_level[0] = self.check_input("\t\tSkill level for vertical precision (distance to bull) (1 to 50)\n\t\t>>>", -1, 50)
                if skill_level[0] == -1:
                    return
                skill_level[1] = self.check_input("\t\tSkill level for azimuthal precision (angle to the sides) (1 to 50)\n\t\t>>>", -1, 50)
                if skill_level[1] == -1:
                    return
                skill_level[2] = self.check_input("\t\tBot speciality (1: None, 2: Scoring, 3: Checkouts; -1: Return\n\t\t>>>", -1, 3)
                if skill_level[2] == -1:
                    return

                if skill_level[2] > 0:
                    skill_level[3] = self.check_input("\t\tSpeciality skills (1 to 5)\n\t\t>>>", -1, 5)
                    if skill_level[3] == -1:
                        return
                else:
                    skill_level[3] = 0
                skill_level[4] = self.check_input("\t\tMental strength (-25 to +25)\n\t\t>>>", -25, 25, False)
                if skill_level[4] == -1:
                    return
                skill_level[5] = self.check_input("\t\tExperience / Experimentation (1 to 50)\n\t\t>>>", -1, 50)
                if skill_level[5] == -1:
                    return
            print("Please wait, while bot's strength is evaluated ... ")
            self.init_autoplay(name=name, skills=skill_level, bot_type=bot_type)
            while True:
                eval_bot = input("Save bot to file? (y=yes, n=no (back to main menu) >>> ")
                if eval_bot.lower() in par.no:
                    return
                elif eval_bot.lower() in par.yes:
                    break

        if bot_type == 2:
            player_type += 1  # introduce player_type = 3 for complex bot recognition
        with open(path + "/" + name + ".drt", 'w') as file:
            file.write("name=%s\n" % name)
            file.write("type=%i\n" % player_type)
            file.write("skill_level={}\n".format(",".join(str(i) for i in skill_level)))
            file.write('Avg=0.0\n')
            file.write('Dtot=0\n')
            file.write('CoAtt=0\n')
            file.write('CoSucc=0\n')
            file.write('CoRat=0.0\n')
            file.write('S100+=0\n')
            file.write('S140+=0\n')
            file.write('S160+=0\n')
            file.write('S180=0\n')
            file.write('T+Out=0\n')
            file.write('HiScore=0\n')
            file.write('HiCo=0\n')
            file.write('AvgCo=0.0')

    def check_input(self, in_in, min_in=None, max_in=None, forbid_zero=True):
        while True:
            answer = input(in_in)
            try:
                answer = int(answer)
            except ValueError:
                if min_in and max_in:
                    self.m.pr("\t# Input must be a number between {:d} and {:d}! Please retry.".format(min_in, max_in))
                else:
                    self.m.pr("\t# Input must be a valid number! Please retry.")
                continue
            if min_in and max_in:
                if answer < min_in or answer > max_in:
                    self.m.pr("\t# Input must be a number between {:d} and {:d}! Please retry.".format(min_in, max_in))
                elif forbid_zero and answer == 0:
                    self.m.pr("\t# Input must not be zero. Please retry.")
                else:
                    return answer


class MainFunction:
    def __init__(self):
        self.ml = MainLoop(self)
        self.pic = plt.imread('Board_cd.png')
        
    def pr(self, message):
        if not self.ml.autoplay:
            print(message)

    def new_game(self, load_paras=None):
        self.gameon = GameOn(self, load_paras)

    def start_loop(self):
        self.ml.user_input()


if __name__ == "__main__":
    m = MainFunction()
    m.start_loop()
