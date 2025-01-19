from __future__ import annotations

# std
import copy
import os
from io import BytesIO
from datetime import datetime

# packages
from PIL import Image, ImageDraw, ImageFont
from infinitode import Player


class Images:
    def __init__(self) -> None:
        # fmt: off
        self.levels = (
            '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8', '1.b1',
            '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8', '2.b1',
            '3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8', '3.b1',
            '4.1', '4.2', '4.3', '4.4', '4.5', '4.6', '4.7', '4.8', '4.b1',
            '5.1', '5.2', '5.3', '5.4', '5.5', '5.6', '5.7', '5.8', '5.b1', '5.b2',
            '6.1', '6.2', '6.3', '6.4', '6.5', 'rumble', 'dev', 'zecred',
            'DQ1', 'DQ3', 'DQ4', 'DQ5', 'DQ7', 'DQ8', 'DQ9', 'DQ10', 'DQ11', 'DQ12',
        )
        # fmt: on
        self.barrier_v = Image.open(
            "assets/images/profile/teleporters/gate-barrier-type-vertical.png"
        )
        self.barrier_h = Image.open(
            "assets/images/profile/teleporters/gate-barrier-type-horizontal.png"
        )
        self.font_lvl = ImageFont.truetype(r"assets/fonts/default/Lato-Regular.ttf", 37)
        self.font_lvl_small = ImageFont.truetype(
            r"assets/fonts/default/Lato-Regular.ttf", 28
        )
        self.font_scores = ImageFont.truetype(
            r"assets/fonts/default/RobotoMono-Regular.ttf", 24
        )
        self.font_progress = ImageFont.truetype(
            r"assets/fonts/default/RobotoMono-Regular.ttf", 48
        )
        self.font_rpl = ImageFont.truetype(r"assets/fonts/default/Lato-Regular.ttf", 48)
        self.small_fonts = ["rumble", "dev", "zecred"]

        self.digits: dict[str, Image.Image] = {}

        for digit in range(0, 10):
            self.digits[str(digit)] = Image.open(
                f"assets/images/profile/levels/{digit}_digit.png"
            )

        self.tp_h: dict[str, Image.Image] = {}
        self.tp_v: dict[str, Image.Image] = {}
        path = "assets/images/profile/teleporters/"

        for filename in os.listdir(path):
            if filename.startswith("gate-teleport-vertical"):
                colour = filename[25:-4]
                if colour.startswith("-"):
                    colour = colour[1:]
                self.tp_v[colour] = Image.open(path + filename)
            elif filename.startswith("gate-teleport-horizontal"):
                colour = filename[27:-4]
                if colour.startswith("-"):
                    colour = colour[1:]
                self.tp_h[colour] = Image.open(path + filename)

        # fmt: off
        self.default_tps: list[list[dict[int, str]]] = [
            # horizontal
            [
                {1: "yellow", 2: "yellow", 3: "yellow", 4: "yellow", 5: "cyan", 6: "cyan", 7: "cyan", 8: "cyan",
                    9: "cyan", 10: "white", 11: "white", 12: "white", 13: "indigo", 14: "indigo", 15: "indigo"},
                {},
                {5: "cyan", 6: "cyan", 7: "cyan", 8: "cyan", 9: "cyan"},
                {5: "teal", 6: "teal", 7: "teal", 8: "teal", 9: "teal"},
                {1: "yellow", 2: "yellow", 3: "yellow", 4: "yellow", 5: "teal", 6: "teal", 7: "teal"},
                {1: "light-blue", 2: "light-blue", 3: "light-blue", 4: "amber", 5: "amber", 6: "amber", 7: "light-green",
                    8: "light-green", 9: "light-green", 10: "purple", 11: "purple", 12: "purple", 13: "red", 14: "red", 15: "red"},
                {}, {}, {}, {},
                {1: "light-blue", 2: "light-blue", 3: "light-blue", 4: "amber", 5: "amber", 6: "amber", 7: "light-green",
                    8: "light-green", 9: "light-green", 10: "purple", 11: "purple", 12: "purple", 13: "red", 14: "red", 15: "red"}
            ],
            # vertical
            [
                {1: "yellow", 2: "yellow", 3: "yellow", 4: "yellow", 5: "teal", 6: "light-blue",
                    7: "light-blue", 8: "light-blue", 9: "light-blue", 10: "light-blue"},
                {}, {},
                {6: "amber", 7: "amber", 8: "amber", 9: "amber", 10: "amber"},
                {1: "yellow", 2: "yellow", 3: "yellow", 4: "yellow"},
                {},
                {6: "light-green", 7: "light-green", 8: "light-green", 9: "light-green", 10: "light-green"},
                {3: "cyan"},
                {},
                {1: "cyan", 2: "cyan", 3: "cyan", 4: "teal", 5: "teal", 6: "purple",
                    7: "purple", 8: "purple", 9: "purple", 10: "purple", },
                {}, {},
                {1: "white", 2: "white", 3: "white", 4: "white", 5: "white",
                    6: "red", 7: "red", 8: "red", 9: "red", 10: "red"},
                {}, {},
                {1: "indigo", 2: "indigo", 3: "indigo", 4: "indigo",
                    5: "indigo", 6: "red", 7: "red", 8: "red", 9: "red", 10: "red"}
            ],
        ]
        # fmt: on

    def profile_gen(
        self,
        player: Player,
        avatar_bytes: bytes | None = None,
        userid: int | None = None,
    ) -> BytesIO:
        """Generates the profile image for the profile command"""
        try:
            bg = Image.open(f"assets/images/profile/custom/{userid}.png")
        except FileNotFoundError:
            bg = Image.open("assets/images/profile/default/default-dev.png")

        badge_keys = list(player.badges.keys())
        badge_values = list(player.badges.values())
        default_tps_h = copy.deepcopy(self.default_tps[0])
        default_tps_v = copy.deepcopy(self.default_tps[1])

        if avatar_bytes:
            pfp = Image.open(BytesIO(avatar_bytes)).resize((512, 512))
        else:
            pfp = Image.open(f"assets/images/profile/default/pfp-default.png")
        bg.paste(pfp, (16, 16))
        write = ImageDraw.Draw(bg)
        font_progress = self.font_progress
        write.text((568, 47), player.nickname, anchor="lt", font=font_progress)
        write.text((568, 120), player.playerid, anchor="lt", font=font_progress)
        write.text(
            (569, 192),
            "{:,}".format(player.total_score),
            anchor="lt",
            font=font_progress,
        )
        write.text(
            (1088, 192),
            "#{:,}".format(player.total_rank),
            anchor="rt",
            font=font_progress,
        )

        scores_x = 276
        scores_x2 = 392
        scores_y = 698
        c = 0

        creation_date = datetime.strptime(player.created_at, "%Y-%m-%d")
        write.text(
            (24, 1260),
            f"EST  {creation_date.strftime('%d.%m.%Y')}",
            anchor="lt",
            font=self.font_scores,
        )

        for level in self.levels:
            level_score = player.score(level)
            write.text(
                (scores_x, scores_y),
                "{:,}".format(level_score.score),
                anchor="rs",
                font=self.font_scores,
            )
            write.text(
                (scores_x2, scores_y),
                "#{:,}".format(int(level_score.rank)),
                anchor="rs",
                font=self.font_scores,
            )
            if level == "zecred":
                write.text(
                    (scores_x2 - 384, scores_y - 192),
                    "{:,}".format(player.replays),
                    anchor="rs",
                    font=self.font_scores,
                )
                write.text(
                    (scores_x2 - 384, scores_y - 128),
                    "{:,}".format(player.issues),
                    anchor="rs",
                    font=self.font_scores,
                )

                scores_y += 64
                s = player.daily_quest
                lvl_score = s.score if s is not None else 0
                lvl_rank = s.rank if s is not None else 0
                write.text(
                    (scores_x, scores_y),
                    "{:,}".format(lvl_score),
                    anchor="rs",
                    font=self.font_scores,
                )
                write.text(
                    (scores_x2, scores_y),
                    "#{:,}".format(lvl_rank),
                    anchor="rs",
                    font=self.font_scores,
                )
                scores_y += 64
                s = player.skill_point
                lvl_score = s.score if s is not None else 0
                lvl_rank = s.rank if s is not None else 0
                write.text(
                    (scores_x, scores_y),
                    "{:,}".format(lvl_score),
                    anchor="rs",
                    font=self.font_scores,
                )
                scores_y = 698 - (5 * 128)
                scores_x += 128 * 3
                scores_x2 += 128 * 3
                c = 0
                continue
            scores_y += 64
            c += 1
            if level == "DQ10":
                c = 2
            elif level == "5.b1":
                c = 8
            elif c == 9:
                scores_y = 698
                scores_x += 128 * 3
                scores_x2 += 128 * 3
                c = 0
            if level == "5.b2":
                scores_y = 698 - (5 * 128)
                scores_x -= 128 * 6
                scores_x2 -= 128 * 6

        path = "assets/images/profile"
        badge_x = 24
        badge_y = 536
        colour_code = {
            "#4CAF50": 1,
            "#5C6BC0": 2,
            "#9C27B0": 3,
            "#FF9800": 4,
            "#00BCD4": 5,
        }
        badge_c = 0
        for badge_name in badge_keys:
            badge_c += 1
            extra = ""
            rar = badge_values[badge_keys.index(badge_name)][0]
            if badge_name == "of-merit":
                extra = "-" + str(
                    colour_code[badge_values[badge_keys.index(badge_name)][1]]
                )

            try:
                badge = Image.open(f"{path}/badges/pb-{rar}-{badge_name}{extra}.png")
            except FileNotFoundError:
                badge_c -= 1
                continue
            
            bg.paste(badge, (badge_x, badge_y), badge)

            if badge_c == 9:
                badge_y -= 128
            elif badge_c == 10:
                badge_x -= 128
            else:
                badge_x += 128

        if badge_c > 5:
            bg.paste(self.barrier_v, (642, 528), self.barrier_v)

            if badge_c > 6:
                bg.paste(self.barrier_v, (770, 528), self.barrier_v)

                if badge_c > 7:
                    bg.paste(self.barrier_v, (898, 528), self.barrier_v)

                    if badge_c > 8:
                        bg.paste(self.barrier_v, (1026, 528), self.barrier_v)

        if badge_c > 9:
            bg.paste(self.barrier_h, (1040, 514), self.barrier_h)

            if badge_c == 11:
                bg.paste(self.barrier_h, (912, 514), self.barrier_h)
                bg.paste(self.barrier_v, (1026, 400), self.barrier_v)
                default_tps_v[7][4] = "teal"

            else:
                default_tps_h[4][8] = "teal"
                default_tps_v[8][4] = "teal"

        else:
            default_tps_h[4][8] = "teal"
            default_tps_h[4][9] = "teal"

        if player.season_level < 150:
            lvl_ico = Image.open(
                f"{path}/levels/player-level-{player.season_level}.png"
            )
        else:
            level = str(player.season_level)
            lvl_ico = Image.open(f"{path}/levels/player-level-max.png")
            xy = 12, 23
            lvl_ico.paste(self.digits[level[0]], xy, self.digits[level[0]])

            xy = 24, 23
            lvl_ico.paste(self.digits[level[1]], xy, self.digits[level[1]])

            xy = 36, 23
            lvl_ico.paste(self.digits[level[2]], xy, self.digits[level[2]])
            lvl_ico = lvl_ico.resize((100, 100))

        bg.paste(lvl_ico, (542, 286), lvl_ico)

        write.text(
            (854, 307),
            "{:} / {:}".format(player.season_xp, player.season_xp_max),
            anchor="rt",
            font=self.font_lvl_small,
        )
        write.rectangle(((656, 346), (890, 364)), fill="#191919")
        x = int((890 - 656) * (player.season_xp / player.season_xp_max) + 656)
        write.rectangle(((656, 346), (x, 364)), fill="#8dc14b")

        level = str(player.level) if player.level < 121 else "120"

        lvl_ico = Image.open(f"{path}/profile-levels/profile-level-{level}.png")
        bg.paste(lvl_ico, (542, 414), lvl_ico)

        write.text(
            (854, 435),
            "{:} / {:}".format(player.xp, player.xp_max),
            anchor="rt",
            font=self.font_lvl_small,
        )
        write.rectangle(((656, 474), (890, 492)), fill="#191919")
        x = int((890 - 656) * (player.xp / player.xp_max) + 656)
        write.rectangle(((656, 474), (x, 492)), fill="#757575")

        x = 16 - 128
        y = 2
        for g in range(11):
            for h in range(15):
                x += 128
                try:
                    colour = default_tps_h[g][h + 1]
                    bg.paste(self.tp_h[colour], (x, y), self.tp_h[colour])
                except KeyError:
                    continue
            x = 16 - 128
            y += 128
        x = 16 - 128
        y = 2
        for g in range(16):
            for h in range(10):
                x += 128
                try:
                    colour = default_tps_v[g][h + 1]
                    bg.paste(self.tp_v[colour], (y, x), self.tp_v[colour])
                except KeyError:
                    continue
            x = 16 - 128
            y += 128

        # default_tps = self.default_tps

        final_buffer = BytesIO()
        bg.save(final_buffer, "png")
        final_buffer.seek(0)

        return final_buffer
