# -*- coding: utf-8 -*-

help_string = """
\t????????? HELP
\tCommand          Impact                                     Example
\t--------------------------------------------------------------------------------
\t#                Regular score                              "26"   : 196 -> 170\n
\t#+x              Regular score with x missed darts
\t                 at a double                                "10+2" : 20  -> 10\n
\ts#               Set to new score                           "s40"  : 84  -> 40\n
\ts#+x             Set to new score with x missed
\t                 darts at a double                          "s8+2" : 32  -> 8\n
\th                Half the score                             "h"    : 40  -> 20\n
\th+x              Half the score with x missed
\t                 darts at a double                          "h+2"  : 40  -> 20\n
\tc                Checkout with single dart                  "c"    : 32  -> 0\n
\tc#               Checkout with # darts                      "c3"   : 167 -> 0\n
\tc#+x             Checkout with # darts and x missed
\t                 darts at a double                          "c2+1" : 48  -> 0\n
\tr                Rewind one visit (+bot)                    "r"    : 25  -> 170\n
\tf                Forward one visit (after rewind)           "f"    : 170 -> 25\n
\thints            Show all suggested paths for 3 darts
\t                 in hand at current score\n
\thints/x/y        Show all suggested paths for x darts
\t                 in hand at score y                         "hints/2/85"\n
\tstats            Show complete game stats for all players\n
\tstats/x[/y]      Show stats for x = l (leg), s(set) or
\t                 m (match) (optional: for player number y)  "stats/m/2", "stats/s"\n
\tsettings         Show/change Settings during the match\n
\tsave             Save current match\n
\tbot_state        Show current state of bot\n
\tabort            Interrupts current game\n
"""

welcome_string = """
                        M. Danner, 2018-2020
############################################
##                                        ##
##  >>==oooo--  COMBAT DARTS  --oooo==<<  ##
##                  v1.0                  ##
##                                        ##
############################################
"""