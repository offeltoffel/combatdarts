# -*- coding: utf-8 -*-

import os
import sys
import numpy as np
import outshots
import time
path = os.path.dirname(os.path.abspath(__file__))

class GameOn:
    def __init__(self, main):
        self.m = main
        self.scores = [self.m.mainloop.x01, self.m.mainloop.x01]
        self.stats_dict = self.m.mainloop.stats_dict
        self.player_string = None
        self.current_player = 0
        self.player_scores = self.m.mainloop.player_scores
        self.rewind_scores = [list(), list()]
        self.assign_skills()
        self.abort = False
        self.attempts = 0
        self.hiscore_evolution = [[list(), list(), list(), list()],
                                  [list(), list(), list(), list()]]  # [["leg, set, match, ever"], ["leg, set, match, ever"]]
        for pl in [0, 1]:
            for i in range(4):
                self.hiscore_evolution[pl][i].append(self.stats_dict[pl]['HiScore'][i+1])
        self.game_loop()

    def assign_skills(self):
        skills = [int(self.m.mainloop.players_dict[0][2]), int(self.m.mainloop.players_dict[1][2])]
        self.scales_rad = [None, None]
        self.scales_azi = [None, None]
        for pl in [0, 1]:
            self.scales_rad[pl] = {"T": self.m.mainloop.skills_dict[skills[pl]][0], "S": self.m.mainloop.skills_dict[skills[pl]][1],
                                   "D": self.m.mainloop.skills_dict[skills[pl]][2], "B": self.m.mainloop.skills_dict[skills[pl]][3]}
            self.scales_azi[pl] = {"T": self.m.mainloop.skills_dict[skills[pl]][4], "S": self.m.mainloop.skills_dict[skills[pl]][5],
                                   "D": self.m.mainloop.skills_dict[skills[pl]][6], "B": self.m.mainloop.skills_dict[skills[pl]][7]}

    def game_loop(self):
        if self.m.mainloop.leg % 2 + self.m.mainloop.set % 2 > 0:
            self.toggle_player()
        if self.m.mainloop.nsets > 1:
            print("set %i of %i; leg %i of %i: Game On!" % (self.m.mainloop.set+1, self.m.mainloop.nsets, self.m.mainloop.leg+1, self.m.mainloop.nlegs))
        else:
            print("leg %i of %i: Game On!" % (self.m.mainloop.leg + 1, self.m.mainloop.nlegs))

        while True:
            player = self.current_player
            game_input = ""
            self.attempts = 0
            self.player_string = "\t%i --> " % self.scores[player]
            if self.m.mainloop.players_dict[player][1] == '1': # human
                game_input = input("Player %i (%s): %i >>> " % (player + 1,
                                                                self.m.mainloop.players_dict[player][0],
                                                                self.scores[player]))
            else: # 'Bot'
                if self.bot_score() == "checkout":
                    break
                else:
                    continue

            if "#" in game_input:
                self.attempts = int(game_input.split('#')[1])
                game_input = game_input.split('#')[0]

            try:
                game_input = int(game_input)
                self.scoring(player=player, score=game_input, mode='regular')
                continue
            except ValueError:
                if game_input.startswith("c"):
                    ndarts = game_input[1:]
                    try:
                        ndarts = int(ndarts)
                        self.checkout(ndarts=ndarts)
                        break
                    except:
                        if ndarts == "":
                            self.checkout()
                            break
                        else:
                            print ("#!# unexpected checkout: '%s'" % ndarts)
                            continue

                elif game_input.startswith("stats"):
                    add = game_input[5:]
                    which = None
                    who = None
                    if not add == "":
                        try:
                            who = int(add)
                        except ValueError:
                            if add.startswith('l'): which = 1
                            elif add.startswith('s'): which = 2
                            elif add.startswith('m'): which = 3
                            else:
                                print("#!# Try 'stats' with 'l', 's' or 'm' + player number")
                                continue

                        if not who:
                            if add[1:] == "":
                                who = None
                            else:
                                try:
                                    who = int(add[1:])
                                except ValueError:
                                    print("#!# Try 'stats' with 'l', 's' or 'm' + player number")
                                    continue

                    self.print_stats(which=which, who=who)
                    continue

                elif game_input.startswith("s"):
                    set_score = game_input[1:]
                    try:
                        set_score = int(set_score)
                    except:
                        print ("#!# unexpected score to set: '%s'" % set_score)
                        set_score = None

                    if set_score:
                        self.scoring(player=player, score=set_score, mode='set')
                    else:
                        continue

                elif game_input == "h":
                    self.scoring(player=player, score=None, mode='half')

                elif game_input == "r":
                    if len(self.player_scores[player][0]) > 0:
                        self.rewind()
                    else:
                        print("No score in memory to rewind!")

                    if self.m.mainloop.players_dict[player][1] == '2' and len(self.player_scores[player][0]) > 0: # if bot threw last and has a valid score to rewind
                        self.rewind()
                    continue

                elif game_input == "f":
                    if len(self.rewind_scores[player]) > 0:
                        print("rewinding score: ", self.rewind_scores[player][-1])
                        self.scoring(player=player, score=self.rewind_scores[player][-1],
                                     mode='restore')
                        self.rewind_scores[player] = self.rewind_scores[player][:-1]
                    else:
                        print("No score in memory to restore!")

                    if self.m.mainloop.settings_dict['botrewind'][1] == -1:
                        player = self.current_player
                        if self.m.mainloop.players_dict[player][1] == '2' and len(self.rewind_scores[player]) > 0:
                            print("rewinding score: ", self.rewind_scores[player][-1])
                            self.scoring(player=player, score=self.rewind_scores[player][-1],
                                         mode='restore')
                            self.rewind_scores[player] = self.rewind_scores[player][:-1]
                    continue

                elif game_input == "abort":
                    self.abort = True
                    break
                else:
                    print("\tno other options yet")

        if self.abort:
            self.m.start_loop()

    def rewind(self):
        self.toggle_player()
        player = self.current_player
        score = self.player_scores[player][0][-1] # get last score
        self.rewind_scores[player].append(score) # append to rewind_scores to be able to restore
        self.scores[player] += score # re-add last score

        for i in [1,2,3,4]:
            self.stats_dict[player]['HiScore'][i] = self.hiscore_evolution[player][i-1][-1]
            del self.hiscore_evolution[player][i-1][-1]
            self.stats_dict[player]['Dtot'][i] -= 3 # no rewind after checkout possible -> ndarts is always 3!
            if i == 4:
                self.stats_dict[player]['Avg'][4] = (((self.stats_dict[player]['Dtot'][4] *
                                                      self.stats_dict[player]['Avg'][4]) +
                                                    (self.stats_dict[player]['Dtot'][3] *
                                                     self.stats_dict[player]['Avg'][3])) /
                                                    (self.stats_dict[player]['Dtot'][3] +
                                                     self.stats_dict[player]['Dtot'][4]))
            else:
                del self.player_scores[player][i-1][-1]
                self.stats_dict[player]['Avg'][i] = (np.sum(self.player_scores[player][i-1]) / self.stats_dict[player]['Dtot'][i]) * 3

            if score == 180:
                self.stats_dict[player]['S180'][i] -= 1
            elif score >= 160:
                self.stats_dict[player]['S160+'][i] -= 1
            elif score >= 140:
                self.stats_dict[player]['S140+'][i] -= 1
            elif score >= 100:
                self.stats_dict[player]['S100+'][i] -= 1

            # if score > self.stats_dict[player]['HiScore'][i]:
            #     self.stats_dict[player]['HiScore'][i] = score

        print("\t%s rewind: %i --> %i" % (self.m.mainloop.players_dict[player][0],
                                          self.scores[player] - score, self.scores[player]))

    def bot_score(self):
        player = self.current_player
        total_botscore = 0
        score = self.scores[player]
        out_dicts = [outshots.co_dict_n1, outshots.co_dict_n2, outshots.co_dict_n3]

        for ndarts in range(2,-1,-1):
            if score > 170:
                aim = "T20"
            else:
                aim = out_dicts[ndarts][score][0] # zunächst nur erster Vorschlag ([0])

            aim_field = aim[0]
            aim_num = int(aim[1:])

            # what the bot aims at
            if aim_field == "T":
                random_rad = np.random.normal(loc=outshots.board_mean_fields["T"], scale=self.scales_rad[player]["T"]) # scale-Wert entscheidet über Genauigkeit!
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num], scale=self.scales_azi[player]["T"])
            elif aim_field == "S":
                random_rad = np.random.normal(loc=outshots.board_mean_fields["S"], scale=self.scales_rad[player]["S"]) # scale-Wert entscheidet über Genauigkeit!
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num], scale=self.scales_azi[player]["S"])
            elif aim_field == "D":
                random_rad = np.random.normal(loc=outshots.board_mean_fields["D"], scale=self.scales_rad[player]["D"])  # scale-Wert entscheidet über Genauigkeit!
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num], scale=self.scales_azi[player]["D"])
            elif aim_field == "B":
                random_rad = abs(np.random.normal(loc=outshots.board_mean_fields[aim],
                                              scale=self.scales_rad[player]["B"]))  # rad für B muss positiv sein, später Umkehr des Winkels!
                random_azi = np.random.normal(loc=outshots.board_mean_nums[aim_num],
                                              scale=self.scales_azi[player]["B"])  # Winkel müssen noch durch Entfernungen ersetzt werden

            ## Check for geometry problems
            if random_rad < 0: # below bulls eye
                random_rad = abs(random_rad)
                random_azi -= 18000 # revert azimuth (correction for <0 follows below)

            if random_azi > 36000: # correction of azimuth for <0° or >360°
                random_azi -= 36000
            elif random_azi < 0:
                random_azi += 36000

            if random_rad > 34000:
                continue

            ## what the bot actually hit
            # Field
            hit_str = ""
            for field in outshots.board_pos_fields: # browse through all possible fields
                if field == "S":
                    if (random_rad > outshots.board_pos_fields["S"][0] and random_rad < outshots.board_pos_fields["S"][1]) \
                            or (random_rad > outshots.board_pos_fields["S"][2] and random_rad < outshots.board_pos_fields["S"][3]):
                        hit_str += "S"
                        break
                else:
                    if (random_rad > outshots.board_pos_fields[field][0] and random_rad < outshots.board_pos_fields[field][1]):
                        hit_str += field[0]
                        break

            # Number
            for number in outshots.board_pos_nums: # browse through all possible fields
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
                    if random_azi > outshots.board_pos_nums[number][0] and random_azi < outshots.board_pos_nums[number][1]:
                        hit_str += str(number)
                        break

            # debug: print randoms:
            # print("random_rad ", random_rad)
            # print("random_azi ", random_azi)

            if (aim_field == "D" and score == aim_num * 2) or (aim_field == "B50" and score == 50):
                self.attempts += 1

            # Calculate actual result of throw
            factor = outshots.field_factors[field[0]]
            bot_throw = factor * number
            total_botscore += bot_throw
            score -= bot_throw

            if score == 0:
                if hit_str==aim:
                    self.attempts -= 1 # successfull co will be added in stats
                    self.checkout(ndarts=abs(ndarts-3))
                    return ("checkout")

            if score < 2:
                total_botscore = 0
                break

        self.scores[self.current_player] -= total_botscore
        self.statistics(player=self.current_player, score=total_botscore, ndarts=3) # ndarts muss noch angepasst werden
        self.toggle_player()

    def checkout(self, ndarts=1):
        ndarts_total = self.stats_dict[self.current_player]['Dtot'][1] + ndarts
        mode="c"+str(ndarts)
        self.scoring(player=self.current_player, score=self.scores[self.current_player], mode=mode)
        print("\t%s won with %i darts!" % (self.m.mainloop.players_dict[self.current_player][0],
                                           ndarts_total))


    def scoring(self, player, score, mode=None):
        score_visit = None
        err = False
        ndarts = 3
        if mode == 'set':
            score_visit = self.scores[player] - score
            if score_visit <= 180:
                self.scores[player] = score
            else: # score apparently has been higher than 180
                print ("\tInvalid score of %i!" % score_visit)
                err = True
        elif mode == 'half':
            score_visit = self.scores[player] // 2
            if self.scores[player] / 2 == score_visit:
                if score_visit <= 180:
                    self.scores[player] //= 2
                else:
                    print("\tInvalid score of %i!" % score_visit)
                    err = True
            else:
                print("\tCannot half an uneven score!")
                err = True
        elif mode.startswith("c"):
            self.statistics(player=player, score=score, ndarts=int(mode[1]), co='yes')
            self.scores[player] = 0
            return
        elif mode == "regular" or mode == "restore":
            score_visit = score
            if score_visit <= 180:
                if self.scores[player] - score_visit <= 1: # Overthrown
                    score_visit = 0
                else:
                    self.scores[player] -= score_visit
            else:
                print("\tInvalid score of %i!" % score_visit)
                err = True
            if not mode == "restore":
                self.rewind_scores[player] = list()

        if not err: # skip this part if an error occured for the scoring routine
            self.statistics(player=player, score=score_visit, ndarts=ndarts)
            self.toggle_player()

    def toggle_player(self):
        if self.current_player == 0:
            self.current_player = 1
        else:
            self.current_player = 0

    def statistics(self, player, score, ndarts=3, co=None):

        for i in [1,2,3,4]:
            self.stats_dict[player]['Dtot'][i] += ndarts
            self.stats_dict[player]['CoAtt'][i] += self.attempts
            if co:
                self.stats_dict[player]['CoAtt'][i] += 1 # successfull checkout = another attempt
                self.stats_dict[player]['CoSucc'][i] += 1
                if score > 100:
                    self.stats_dict[player]['T+Out'][i] += 1
                if self.stats_dict[player]['CoSucc'][i] == 1: # first checkout on this level
                    self.stats_dict[player]['AvgCo'][i] = score
                else:
                    self.stats_dict[player]['AvgCo'][i] = (self.stats_dict[player]['AvgCo'][i] *
                                                           (self.stats_dict[player]['CoSucc'][i] - 1) + score) \
                                                          / self.stats_dict[player]['CoSucc'][i]


            try:
                self.stats_dict[player]['CoRat'][i] = self.stats_dict[player]['CoSucc'][i]*100 / self.stats_dict[player]['CoAtt'][i]
            except ZeroDivisionError:
                self.stats_dict[player]['CoRat'][i] = 0.0
            if i == 4:
                self.stats_dict[player]['Avg'][4] = (((self.stats_dict[player]['Dtot'][4] *
                                                       self.stats_dict[player]['Avg'][4]) +
                                                      (self.stats_dict[player]['Dtot'][3] *
                                                       self.stats_dict[player]['Avg'][3])) /
                                                     (self.stats_dict[player]['Dtot'][3] +
                                                      self.stats_dict[player]['Dtot'][4]))
            else:
                self.player_scores[player][i-1].append(score)
                self.stats_dict[player]['Avg'][i] = (np.sum(self.player_scores[player][i-1]) / self.stats_dict[player]['Dtot'][i]) * 3

            if score == 180:
                self.stats_dict[player]['S180'][i] += 1
            elif score >= 160:
                self.stats_dict[player]['S160+'][i] += 1
            elif score >= 140:
                self.stats_dict[player]['S140+'][i] += 1
            elif score >= 100:
                self.stats_dict[player]['S100+'][i] += 1

            if score > self.stats_dict[player]['HiScore'][i]:
                self.hiscore_evolution[player][i-1].append(score) # new highscore on level, add to highscore_list
                self.stats_dict[player]['HiScore'][i] = score
            else:
                self.hiscore_evolution[player][i-1].append(self.hiscore_evolution[player][i-1][-1]) # no new highscore on level, repeat last value


        if co: # we have a checkout - clean up
            self.m.mainloop.wins[player][0] += 1
            self.m.mainloop.wins[player][1] += 1
            if self.m.mainloop.wins[player][1] == self.m.mainloop.legs_needed:
                where = [1, 2] # set is finished, clean set too
                self.m.mainloop.wins[player][0] += 1
                self.m.mainloop.wins[0][1] = 0
                self.m.mainloop.wins[1][1] = 0
                self.m.mainloop.wins[player][2] += 1
            else:
                where = [1] # leg is finished, clean only leg

            for pl in [0, 1]:
                for w in where:
                    self.player_scores[pl][w-1] = list()
                    for key in self.stats_dict[player]:
                        self.stats_dict[pl][key][w] = 0
            if 2 in where:
                self.print_stats(which=3)
                print("***")
                # print(self.m.mainloop.radT, self.m.mainloop.radS, self.m.mainloop.radD, self.m.mainloop.radB)
                # print(self.m.mainloop.aziT, self.m.mainloop.aziS, self.m.mainloop.aziD, self.m.mainloop.aziB)
                exit()

    def print_matchscore(self):
        print("++++")
        print("\tMatch Score (%s vs. %s):" % (self.m.mainloop.players_dict[0][0], self.m.mainloop.players_dict[1][0]))
        if self.m.mainloop.nsets > 1:
            print("\t\tSets: %i - %i" %(self.m.mainloop.wins[0][2], self.m.mainloop.wins[1][2]))
        print("\t\tLegs: %i - %i" % (self.m.mainloop.wins[0][1], self.m.mainloop.wins[1][1]))
        print("++++")


    def print_stats(self, which=None, who=None):
        if not who:
            who = [0, 1]
        else:
            who = [who-1]

        if not which:
            which = [1, 2, 3]
        else:
            which = [which]

        labels = ['dummy', 'leg', 'set', 'match']
        for player in who:
            print("++++")
            print("\tStatistics for player %i (%s)" % (player + 1, self.m.mainloop.players_dict[player][0]))
            for level in which:
                print("\t++")
                print("\t\tAverage (%s): %6.2f" % (labels[level], self.stats_dict[player]['Avg'][level]))
                print("\t\tScore 100+ (%s): %i" % (labels[level], self.stats_dict[player]['S100+'][level]))
                print("\t\tScore 140+ (%s): %i" % (labels[level], self.stats_dict[player]['S140+'][level]))
                print("\t\tScore 160+ (%s): %i" % (labels[level], self.stats_dict[player]['S160+'][level]))
                print("\t\tScore 180s (%s): %i" % (labels[level], self.stats_dict[player]['S180'][level]))
                print("\t\tHighest Score (%s): %i" % (labels[level], self.stats_dict[player]['HiScore'][level]))
                print("\t\tCheckout Attempts (%s): %i" % (labels[level], self.stats_dict[player]['CoAtt'][level]))
                print("\t\tCheckouts Successfull (%s): %i" % (labels[level], self.stats_dict[player]['CoSucc'][level]))
                print("\t\tCheckout Rate (%s): %i" % (labels[level], self.stats_dict[player]['CoRat'][level]))
        print("++++")


class MainLoop:
    def __init__(self, main):
        self.m = main
        self.skills_dict = None
        self.skills()

    def skills(self):
        skills = list()
        higher = [4000, 4000, 4000, 5000, 630, 700, 700, 800]
        lower = [1500, 1500, 1500, 1750, 170, 180, 180, 190]
        for skill_level in range(50):
            skills.append(list())
            for field in range(8):
                skills[skill_level].append(higher[field] + ((lower[field] - higher[field]) / 49) * skill_level)
        self.skills_dict = dict(zip(range(1, 51), skills))
        self.skills_dict[-1] = ([[-1 for i in range(8)] for j in range(50)])

    def reset(self):
        self.players = list()
        self.nplayers = None
        self.players_dict = None
        self.settings_dict = None
        self.playerA_stats = {'Avg':     [['Avg', 'fl'], 0, 0, 0, 0],
                              'Dtot':    [['Darts in total', 'int'], 0, 0, 0, 0],
                              'CoAtt':   [['Checkout - attempts', 'int'], 0, 0, 0, 0],
                              'CoSucc':  [['Checkout - successfull', 'int'], 0, 0, 0, 0],
                              'CoRat':   [['Checkout - percentage', 'fl'], 0, 0, 0, 0],
                              'S100+':   [['Score 100+', 'int'], 0, 0, 0, 0],
                              'S140+':   [['Score 140+', 'int'], 0, 0, 0, 0],
                              'S160+':   [['Score 160+', 'int'], 0, 0, 0, 0],
                              'S180':    [['Score 180+', 'int'], 0, 0, 0, 0],
                              'T+Out':   [['Outshots 100+', 'int'], 0, 0, 0, 0],
                              'HiScore': [['Highest Score', 'int'], 0, 0, 0, 0],
                              'HiCo':    [['Highest Checkout', 'int'], 0, 0, 0, 0],
                              'AvgCo':   [['Average Checkout', 'fl'], 0, 0, 0, 0]}

        self.playerB_stats = {'Avg':     [['Avg', 'fl'], 0, 0, 0, 0],
                              'Dtot':    [['Darts in total', 'int'], 0, 0, 0, 0],
                              'CoAtt':   [['Checkout - attempts', 'int'], 0, 0, 0, 0],
                              'CoSucc':  [['Checkout - successfull', 'int'], 0, 0, 0, 0],
                              'CoRat':   [['Checkout - percentage', 'fl'], 0, 0, 0, 0],
                              'S100+':   [['Score 100+', 'int'], 0, 0, 0, 0],
                              'S140+':   [['Score 140+', 'int'], 0, 0, 0, 0],
                              'S160+':   [['Score 160+', 'int'], 0, 0, 0, 0],
                              'S180':    [['Score 180+', 'int'], 0, 0, 0, 0],
                              'T+Out':   [['Outshots 100+', 'int'], 0, 0, 0, 0],
                              'HiScore': [['Highest Score', 'int'], 0, 0, 0, 0],
                              'HiCo':    [['Highest Checkout', 'int'], 0, 0, 0, 0],
                              'AvgCo':   [['Average Checkout', 'fl'], 0, 0, 0, 0]}

        self.stats_dict = [self.playerA_stats, self.playerB_stats]

    def new_game(self):
        self.read_settings()
        self.read_players()
        player1 = 1
        player2 = 6

        # self.scales_rad = {"T": 3000.0, "S": 3500.0, "D": 2000.0, "B": 4000.0} # hard code until dynamic calculation of skills
        # self.scales_azi = {"T": 1000.0, "S": 1000.0, "D": 700.0, "B": 1000.0}

        self.open_players(p=[self.players[player1-1], self.players[player2-1]])
        x01 = 5
        self.x01 = x01*100 + 1

        self.nsets = 1
        while True:
            self.nlegs = 301
            if self.nlegs % 2 > 0:
                break
            else:
                print ("Number of legs needs to be uneven number!")

        # initialize lists
        self.player_scores = [[[], [], []], [[], [], []]]
        self.wins = [[0, 0, 0], [0, 0, 0]] # wins[player][legs_total, legs, sets]

        for set in range(self.nsets):
            if self.wins[0][2] == (self.nsets // 2) + 1 or self.wins[1][2] == (self.nsets // 2) + 1:
                break
            self.set = set
            self.legs_needed = (self.nlegs // 2) + 1
            for leg in range(self.nlegs):
                if self.settings_dict['savstats'][1] == 1:
                    self.save_stats()
                self.leg = leg
                self.m.new_game()

        # Game finished:
        self.save_stats()

    def user_input(self):
        while True:
            self.reset()
            self.read_settings()
            user_in = 1

            if user_in == 1:
                self.new_game()
            if user_in == 2:
                self.new_player()
            if user_in == 4:
                self.settings()
            if user_in == 5:
                exit()

    def settings(self):
        onoff = {-1: "off", 1: "on"}
        while True:
            print("~~~")
            keykey = list()
            for i, key in enumerate(self.settings_dict):
                keykey.append(key)
                print("%i: %s - %s" % (i+1, self.settings_dict[key][0], onoff[self.settings_dict[key][1]]))
            print("%i: Return" % (len(self.settings_dict)+1))
            settings_input = input("Toggle On/Off [#] >>> ")
            try:
                settings_input = int(settings_input)-1
            except ValueError:
                print("Invalid Input")
                return
            if settings_input == len(self.settings_dict):
                self.save_settings()
                return
            key = keykey[settings_input]
            self.settings_dict[key][1] *= -1 # toggle Setting
            self.save_settings()

    def save_settings(self):
        with open(path+"/Settings.dat", 'w') as settings_file:
            for key in self.settings_dict:
                save_string = "%s=%s=%i\n" % (key, self.settings_dict[key][0], self.settings_dict[key][1])
                settings_file.write(save_string)

    def read_settings(self):
        with open(path+"/Settings.dat", 'r') as settings_file:
            content = settings_file.readlines()
        content = [item.rstrip() for item in content]
        settings_parameter, settings_label_val = (list(), list())
        for item in content:
            settings_parameter.append(item.split('=')[0])
            settings_label_val.append([item.split('=')[1], int(item.split('=')[2])])
        self.settings_dict = dict(zip(settings_parameter, settings_label_val))

    def read_players(self):
        dir = os.listdir(path=path)
        for file in dir:
            if file.endswith(".drt"):
                self.players.append(file)
        self.nplayers = len(self.players)

    def open_players(self, p):
        pl_content = [list(), list()]
        for pl in [0,1]:
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
        self.players_dict = dict(zip([0, 1], pl_content))

    def save_stats(self):
        for player in [0,1]:
            with open(path+"/"+self.players_dict[player][0]+'.drt', 'w') as file:
                file.write("name=%s\n" % self.players_dict[player][0])
                file.write("type=%s\n" % str(self.players_dict[player][1]))
                file.write("skill=%s\n" % str(self.players_dict[player][2]))
                for i, key in enumerate(self.stats_dict[player]):
                    file.write("%s=%s\n" % (key, str(self.stats_dict[player][key][4])))

    def new_player(self):
        name = input("Name of Player\n>>> ")
        player_type = int(input("1: Human Player; 2: Computer Player\n>>> "))
        skill_level = -1
        if player_type == 2:
            skill_level = int(input("Skill level (1-20)\n>>> "))
        with open(path +"/" + name + ".drt", 'w') as file:
            file.write("name=%s\n" % name)
            file.write("type=%i\n" % player_type)
            file.write("skill_level=%i" % skill_level)
            file.write('Avg=0.0')
            file.write('Dtot=0')
            file.write('CoAtt=0')
            file.write('CoSucc=0')
            file.write('CoRat=0.0')
            file.write('S100+=0')
            file.write('S140+=0')
            file.write('S160+=0')
            file.write('S180=0')
            file.write('T+Out=0')
            file.write('HiScore=0')
            file.write('HiCo=0')
            file.write('AvgCo=0.0')

class MainFunction:
    def __init__(self):
        self.mainloop = MainLoop(self)

    def new_game(self):
        self.gameon = GameOn(self)

    def start_loop(self):
        self.mainloop.user_input()

if __name__ == "__main__":
    m = MainFunction()
    m.start_loop()



# 4000 4000 4000 5000
# 1500 1500 1500 1750
# Average (match):  26.1
# Checkout Rate (match): 7

# 630 700 700 800
# 170 180 180 190

# Average (match): 108.5
# Checkout Rate (match): 76
