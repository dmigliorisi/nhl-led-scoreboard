from PIL import Image, ImageFont, ImageDraw, ImageSequence
from time import sleep
import time
from datetime import datetime
import debug
from boards.boards import Boards
from boards.clock import Clock
from data.scoreboard import Scoreboard
from renderer.scoreboard import ScoreboardRenderer
from utils import get_file
import serial

class Refreshing_data(object):
    pass


class MainRenderer:
    def __init__(self, matrix, data):
        self.matrix = matrix
        self.data = data
        self.status = self.data.status
        self.refresh_rate = self.data.config.live_game_refresh_rate
        self.boards = Boards()
        self.ser = serial.Serial('/dev/ttyACM0', 19200, timeout=1)
        self.runtime_start = 0
        self.font_woo = ImageFont.truetype(get_file("assets/fonts/Bungee-Regular.otf"), 24)

    def render(self):
        # flush the serial communication
        self.ser.flush()
        self.runtime_start = int(round(time.time()))
        debug.info(self.runtime_start)

        while self.data.network_issues:
            Clock(self.data, self.matrix, duration=60)
            self.data.refresh_data()

        while True:
            try:
                debug.info('Rendering...')
                if self.status.is_offseason(self.data.date()):
                    # Offseason (Show offseason related stuff)
                    debug.info("It's offseason")
                    self.__render_offday()
                else:
                    # Season.
                    if not self.data.config.live_mode:
                        debug.info("Live mode is off. Going through the boards")
                        self.__render_game_day()
                        self.__render_offday()
                    elif self.data.is_pref_team_offday():
                        debug.info("Your preferred teams are Off today")
                        self.__render_offday()
                    elif self.data.is_nhl_offday():
                        debug.info("There is no game in the NHL today")
                        self.__render_offday()
                    else:
                        debug.info("Game Day Wooooo")
                        self.__render_game_day()

            except AttributeError as e:
                debug.log("ERROR WHILE RENDERING: "+e)
                debug.log("Refreshing data in a minute")
                self.boards.fallback(self.data, self.matrix)
                self.data.refresh_data()
                self.status = self.data.status


    def __render_offday(self):
        while True:
            debug.log('PING !!! Render off day')
            if self.data._is_new_day():
                debug.info('This is a new day')
                return
            self.data.refresh_games()
            self.data.refresh_standings()
            self.boards._off_day(self.data, self.matrix)

    def __render_game_day(self):
        debug.info("Showing Game")
        # Initialize the scoreboard. get the current status at startup
        self.data.refresh_overview()
        self.scoreboard = Scoreboard(self.data.overview, self.data.teams_info, self.data.config)
        self.away_score = self.scoreboard.away_team.goals
        self.home_score = self.scoreboard.home_team.goals
        while True:

            if self.data._is_new_day():
                debug.log('This is a new day')
                return

            if self.data.needs_refresh:
                print("refreshing")
                self.data.refresh_current_date()
                self.data.refresh_overview()
                self.data.refresh_games()
                self.data.refresh_standings()
                if self.data.network_issues:
                    self.matrix.network_issue_indicator()

            if self.status.is_live(self.data.overview.status):
                """ Live Game state """
                debug.info("Game is Live")
                self.scoreboard = Scoreboard(self.data.overview, self.data.teams_info, self.data.config)
                self.check_new_goals()
                self.__render_live(self.scoreboard)

            elif self.status.is_final(self.data.overview.status):
                """ Post Game state """
                debug.info("Game Over")
                self.scoreboard = Scoreboard(self.data.overview, self.data.teams_info, self.data.config)
                self.__render_postgame(self.scoreboard)


            elif self.status.is_scheduled(self.data.overview.status):
                """ Pre-game state """
                debug.info("Game is Scheduled")
                self.scoreboard = Scoreboard(self.data.overview, self.data.teams_info, self.data.config)
                self.__render_pregame(self.scoreboard)


    def __render_pregame(self, scoreboard):
#         debug.info("Showing Main Event")
        self.matrix.clear()
        ScoreboardRenderer(self.data, self.matrix, scoreboard).render()
        sleep(self.refresh_rate)
        self.boards._scheduled(self.data, self.matrix)
        self.data.needs_refresh = True

    def __render_postgame(self, scoreboard):
        debug.info("Showing Post-Game")
        self.matrix.clear()
        ScoreboardRenderer(self.data, self.matrix, scoreboard).render()
        self.draw_end_period_indicator()
        sleep(self.refresh_rate)
        self.boards._post_game(self.data, self.matrix)
        self.data.needs_refresh = True

    def __render_live(self, scoreboard):
#         debug.info("Showing Main Event")
        self.matrix.clear()
        ScoreboardRenderer(self.data, self.matrix, scoreboard).render()
        if scoreboard.intermission:
            debug.info("Main event is in Intermission")
            # Show Boards for Intermission
            self.draw_end_period_indicator()
            sleep(self.refresh_rate)
            self.boards._intermission(self.data, self.matrix)
        else:

        if self.ser.in_waiting > 0:
            line = self.ser.readline().decode('utf-8').rstrip()
            debug.info(line)
            if line == "1":
                self._draw_goal_light_display()
            elif line == "2":
                # draw pp animation
                self._draw_goal_light_display()
            elif line == "3":
                # draw josh bailey
                self._draw_jb_animation()
                sleep(6.75)
                self._draw_jb_animation()
            elif line == "4":
                debug.info("Pageau")
                # draw pageau animation
                self._draw_pageau_animation()
            elif line == "5":
                # draw the rangers suck
                self.draw_scroll_text("CHAARGEE")
            elif line == "6":
                # draw the rangers suck
                self.draw_scroll_text("The Rangers Suck")

        if self.runtime_start + self.refresh_rate  < int(round(time.time())):
            self.data.needs_refresh = True
            self.runtime_start = int(round(time.time()))


    def check_new_goals(self):
        debug.log("Check new goal")
        if self.away_score < self.scoreboard.away_team.goals:
            self.away_score = self.scoreboard.away_team.goals
            self._draw_goal(self.scoreboard.away_team.id, self.scoreboard.away_team.name)
        if self.home_score < self.scoreboard.home_team.goals:
            self.home_score = self.scoreboard.home_team.goals
            self._draw_goal(self.scoreboard.home_team.id, self.scoreboard.home_team.name)

    def _draw_goal(self, id, name):
        debug.info('Score by team: ' + name)
        # Set opposing team goal animation here
        filename = "assets/animations/goal_light_animation.gif"
        if id in self.data.pref_teams:
            # Set your preferred team goal animation here
            filename = "assets/animations/goal_light_animation.gif"

        im = Image.open(get_file(filename))

        # Set the frame index to 0
        frame_nub = 0

        self.matrix.clear()

        # Go through the frames
        x = 0
        while x is not 5:
            try:
                im.seek(frame_nub)
            except EOFError:
                x += 1
                frame_nub = 0
                im.seek(frame_nub)

            self.matrix.draw_image((0, 0), im)
            self.matrix.render()

            frame_nub += 1
            sleep(0.1)

    def draw_end_period_indicator(self):
        """TODO: change the width depending how much time is left to the intermission"""
        color = self.matrix.graphics.Color(0, 255, 0)
        self.matrix.graphics.DrawLine(self.matrix.matrix, 23, self.matrix.height - 2, 39, self.matrix.height - 2, color)
        self.matrix.graphics.DrawLine(self.matrix.matrix, 22, self.matrix.height - 1, 40, self.matrix.height - 1, color)

    def _draw_pageau_animation(self):
        self.draw_scroll_text("PAGEAU")
        sleep(2)
        self.draw_blank_rect()
        self.draw_static_text("PAGEAU", 13)
        sleep(0.5)
        self.draw_blank_rect()
        self.draw_static_text("PAGEAU", 13)
        sleep(0.5)
        self.draw_blank_rect()
        self.draw_static_text("PAGEAU", 13)


    def _draw_jb_animation(self):
        self.draw_scroll_text("HEEEEEY")
        sleep(1.5)
        self.draw_static_text("JOSH", 28)
        sleep(0.25)
        self.draw_static_text("BAILEY", 12)
        sleep(0.5)
        self.draw_scroll_text("OOOOOOOOO")
        self.draw_scroll_text("AHHHHHHHH")
        self.matrix.clear()
        sleep(1)
        self.matrix.clear()

    def _draw_goal_light_display(self):
        loopGoal = 0

        while loopGoal <  30:
            loopGoal = loopGoal + 1
            self.draw_blank_rect()
            sleep(0.5)
            self.draw_goal_sign()
            sleep(0.5)


        # Loops through the WoOoOoOos
        loopWoo = 0
        while loopWoo < 3:
            loopWoo = loopWoo + 1
            self.draw_scroll_text("woooooooo")
            sleep(0.5)

        # Clears the screen
        self.draw_blank_rect()
        sleep(5.5)

        # Yes! Yes! Yes!
        loopYes = 0
        while loopYes < 10:
            sleep(0.15)
            loopYes = loopYes + 1
            self.draw_yes()
            sleep(0.15)
            self.draw_blank_rect()


    def draw_scroll_text(self, word):
        self.matrix.clear()

        # Create a new data image.
        imageWidth = 256
        image = Image.new('RGB', (256, 32 ))
        draw = ImageDraw.Draw(image)

        draw.rectangle([(0,0),(256, 32)], fill=(0, 83, 155))
        draw.text((129, 4), word, font=self.font_woo)
        draw.text((130, 5), word, fill=(244, 125, 48), font=self.font_woo)
        self.matrix.draw_image((0, 0), image)
        self.matrix.render()
        sleep(0.2)

        i = 0
        # Move the image up until we hit the bottom.
        while i > -(imageWidth - self.matrix.width):
            i -= 8
            self.matrix.draw_image((i, 0), image)
            self.matrix.render()

    def draw_yes(self):
        self.matrix.clear()
        image = Image.new('RGB', (self.matrix.width, self.matrix.height))

        # draw the Yes
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0,0), (128, 32)], fill=(0, 83, 155))

        draw.text((4, 3), "YES!", font=self.font_woo)
        draw.text((5, 4), "YES!", font=self.font_woo, fill=(244, 125, 48))

        draw.text((66, 3), "YES!", font=self.font_woo)
        draw.text((67, 4), "YES!", font=self.font_woo, fill=(244, 125, 48))

        self.matrix.draw_image((0, 0), image)
        self.matrix.render()

    def draw_static_text(self, text, pos):
        self.matrix.clear()
        image = Image.new('RGB', (self.matrix.width, self.matrix.height))

        # draw the text
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0,0), (128, 32)], fill=(0, 83, 155))

        draw.text((pos, 3), text, font=self.font_woo)
        draw.text((pos+1, 4), text, font=self.font_woo, fill=(244, 125, 48))
        self.matrix.draw_image((0, 0), image)
        self.matrix.render()


    def draw_blank_rect(self):
        self.matrix.clear()
        image = Image.new('RGB', (self.matrix.width, self.matrix.height))

        # draw the blank blue rectangle
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0,0), (128, 32)], fill=(0, 83, 155))

        self.matrix.draw_image((0, 0), image)
        self.matrix.render()

    def draw_goal_sign(self):
        self.matrix.clear()
        image = Image.new('RGB', (self.matrix.width, self.matrix.height))

        # draw the blank blue rectangle
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0,0), (128, 32)], fill=(0, 83, 155))

        draw.text((28, 3), "GOAL", font=self.font_woo)
        draw.text((30, 5), "GOAL", font=self.font_woo, fill=(244, 125, 48))

        self.matrix.draw_image((0, 0), image)
        self.matrix.render()

