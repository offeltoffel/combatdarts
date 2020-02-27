# -*- coding: utf-8 -*-

help_string = """
\t????????? HELP
\tCommand             Impact                                   Example
\t--------------------------------------------------------------------------------
\t#                   Regular score                            "26"   : 196 -> 170
\t#+x                 Regular score with x missed darts
\t                    at a double                              "10+2" : 20  -> 10
\ts#                  Set to new score                         "s40"  : 84  -> 40
\ts#+x                Set to new score with x missed
\t                    darts at a double                        "s8+2" : 32 -> 8
\th                   Half the score                           "h"    : 40  -> 20
\tc                   Checkout with single dart                "c"    : 32  -> 0
\tc#                  Checkout with # darts                    "c3"   : 167 -> 0
\tc#+x                Checkout with # darts and x missed
\t                    darts at a double                        "c2+1" : 48  -> 0
\tabort               Interrupts current game
\tbot_state           Show current state of bot
"""