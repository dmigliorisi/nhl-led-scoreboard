from PIL import Image, ImageFont, ImageDraw, ImageSequence
from time import sleep
import time
from datetime import datetime
import debug
from boards.boards import Boards
from boards.clock import Clock
from data.scoreboard import Scoreboard
from renderer.scoreboard import ScoreboardRenderer
from renderer.goal import GoalRenderer
from renderer.fanfare import Fanfare
from utils import get_file
import serial
import random
import glob

class MainRenderer:
    def __init__(self, matrix, data, sleepEvent):
        self.fanfare = Fanfare(data, matrix)
        self.matrix = matrix
        self.data = data
        self.status = self.data.status
        self.refresh_rate = self.data.config.live_game_refresh_rate
        self.boards = Boards()
        self.ser = serial.Serial('/dev/ttyACM0', 19200, timeout=1)
        self.runtime_start = 0
        self.font_woo = ImageFont.truetype(get_file("assets/fonts/Bungee-Regular.otf"), 24)
        self.sleepEvent = sleepEvent
        self.sog_display_frequency = data.config.sog_display_frequency
        self.alternate_data_counter = 1


    def render(self):
        # flush the serial communication
        self.ser.flush()
        self.runtime_start = int(round(time.time()))
        debug.info(self.runtime_start)

        while self.data.network_issues:
            Clock(self.data, self.matrix, self.sleepEvent, duration=60)
            self.data.refresh_data()

        while True:
            self.fanfare.listenForSerial()
            try:
                debug.info('Rendering...')
                self.data.refresh_data()

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
                debug.log(f"ERROR WHILE RENDERING: {e}")
                debug.log("Refreshing data in a minute")
                self.boards.fallback(self.data, self.matrix, self.sleepEvent)
                self.data.refresh_data()


    def __render_offday(self):
        while True:
            debug.log('PING !!! Render off day')
            if self.data._is_new_day():
                debug.info('This is a new day')
                return
            self.data.refresh_data()
            
            self.boards._off_day(self.data, self.matrix,self.sleepEvent)

    def __render_game_day(self):
        debug.info("Showing Game")
        # Initialize the scoreboard. get the current status at startup
        self.data.refresh_overview()
        self.scoreboard = Scoreboard(self.data.overview, self.data)
        self.away_score = self.scoreboard.away_team.goals
        self.home_score = self.scoreboard.home_team.goals
        # Cache to save goals and allow all the details to be collected on the API.
        self.goal_team_cache = []
        self.sleepEvent.clear()

        while True:

            if self.data._is_new_day():
                debug.log('This is a new day')
                return

            # Display the pushbutton board
            if self.data.pb_trigger:
                debug.info('PushButton triggered in game day loop....will display ' + self.data.config.pushbutton_state_triggered1 + ' board')
                self.data.pb_trigger = False
                #Display the board from the config
                self.boards._pb_board(self.data, self.matrix, self.sleepEvent)

            # Display the Weather Alert board
            if self.data.wx_alert_interrupt:
                debug.info('Weather Alert triggered in game day loop....will display weather alert board')
                self.data.wx_alert_interrupt = False
                #Display the board from the config
                self.boards._wx_alert(self.data, self.matrix, self.sleepEvent)

            if self.status.is_live(self.data.overview.status):
                """ Live Game state """
                debug.info("Game is Live")
                self.scoreboard = Scoreboard(self.data.overview, self.data)
                self.check_new_goals()
                self.__render_live(self.scoreboard)
                if self.scoreboard.intermission:
                    debug.info("Main event is in Intermission")
                    # Show Boards for Intermission
                    self.draw_end_period_indicator()
                    self.sleepEvent.wait(self.refresh_rate)
                    self.check_new_goals()
                    self.boards._intermission(self.data, self.matrix,self.sleepEvent)
                else:
                    self.sleepEvent.wait(self.refresh_rate)

            elif self.status.is_game_over(self.data.overview.status):
                print(self.data.overview.status)
                debug.info("Game Over")
                self.scoreboard = Scoreboard(self.data.overview, self.data)
                self.check_new_goals()
                self.__render_postgame(self.scoreboard)
                # sleep(self.refresh_rate)
                self.sleepEvent.wait(self.refresh_rate)

            elif self.status.is_final(self.data.overview.status):
                """ Post Game state """
                debug.info("FINAL")
                self.scoreboard = Scoreboard(self.data.overview, self.data)
                self.check_new_goals()
                
                self.__render_postgame(self.scoreboard)

                self.sleepEvent.wait(self.refresh_rate)
                if self.data._next_game():
                    debug.info("moving to the next preferred game")
                    return
                if not self.goal_team_cache:
                    self.boards._post_game(self.data, self.matrix,self.sleepEvent)

            elif self.status.is_scheduled(self.data.overview.status):
                """ Pre-game state """
                debug.info("Game is Scheduled")
                self.scoreboard = Scoreboard(self.data.overview, self.data)
                self.__render_pregame(self.scoreboard)
                #sleep(self.refresh_rate)
                self.sleepEvent.wait(self.refresh_rate)
                self.boards._scheduled(self.data, self.matrix,self.sleepEvent)

            elif self.status.is_irregular(self.data.overview.status):
                """ Pre-game state """
                debug.info("Game is irregular")
                self.scoreboard = Scoreboard(self.data.overview, self.data)
                self.__render_irregular(self.scoreboard)
                #sleep(self.refresh_rate)
                self.sleepEvent.wait(self.refresh_rate)
                self.boards._scheduled(self.data, self.matrix,self.sleepEvent)

            if self.runtime_start + self.refresh_rate  < int(round(time.time())):
                self.data.needs_refresh = True
                self.runtime_start = int(round(time.time()))
                self.data.refresh_data()
                self.data.refresh_overview()
        
            if self.data.network_issues:
                self.matrix.network_issue_indicator()
            
            if self.data.newUpdate and not self.data.config.clock_hide_indicators:
                self.matrix.update_indicator()


    def __render_pregame(self, scoreboard):
        debug.info("Showing Pre-Game")
        self.matrix.clear()
        ScoreboardRenderer(self.data, self.matrix, scoreboard).render()


    def __render_postgame(self, scoreboard):
        debug.info("Showing Post-Game")
        self.matrix.clear()
        ScoreboardRenderer(self.data, self.matrix, scoreboard).render()
        self.draw_end_of_game_indicator()


    def __render_live(self, scoreboard):
#         debug.info("Showing Main Event")
        self.matrix.clear()
        show_SOG = False
        if self.alternate_data_counter % self.sog_display_frequency == 0:
            show_SOG = True
        ScoreboardRenderer(self.data, self.matrix, scoreboard, show_SOG).render()
        self.alternate_data_counter += 1

    def __render_irregular(self, scoreboard):
        debug.info("Showing Irregular")
        self.matrix.clear()
        ScoreboardRenderer(self.data, self.matrix, scoreboard).render()
        if scoreboard.intermission:
            debug.info("Main event is in Intermission")
            # Show Boards for Intermission
            self.draw_end_period_indicator()
            sleep(self.refresh_rate)
            self.boards._intermission(self.data, self.matrix)

    def check_new_goals(self):
        debug.log("Check new goal")
        
        pref_team_only = self.data.config.goal_anim_pref_team_only
        away_id = self.scoreboard.away_team.id
        away_name = self.scoreboard.away_team.name
        away_goals = self.scoreboard.away_team.goals
        away_score = self.away_score
        home_id = self.scoreboard.home_team.id
        home_name = self.scoreboard.home_team.name
        home_goals = self.scoreboard.home_team.goals
        home_score = self.home_score
        # Display goal details that are cached if there is any
        # GoalRenderer(self.data, self.matrix, self.sleepEvent, self.scoreboard.away_team).render()
        if self.goal_team_cache:
            try:
                while self.goal_team_cache:
                    # create a goal object first to see if there are any missing data
                    if self.goal_team_cache[0] == "away":
                        GoalRenderer(self.data, self.matrix, self.sleepEvent, self.scoreboard.away_team).render()
                    else:
                        GoalRenderer(self.data, self.matrix, self.sleepEvent, self.scoreboard.home_team).render()
                    # Remove the first cached goal
                    self.goal_team_cache.pop(0)
            except IndexError:
                debug.error("The scoreboard object failed to get the goal details, trying on the next data refresh")

        if away_score < away_goals:
            self.away_score = away_goals
            self.goal_team_cache.append("away")
            if away_id not in self.data.pref_teams and pref_team_only:
                return
            # run the goal animation
            self._draw_goal_animation(away_id, away_name)
            

        if home_score < home_goals:
            self.home_score = home_goals
            self.goal_team_cache.append("home")
            if home_id not in self.data.pref_teams and pref_team_only:
                return
            # run the goal animation
            self._draw_goal_animation(away_id, home_name)
            
    
    def _draw_goal_animation(self, id=14, name="test"):
        debug.info('Score by team: ' + name)

        # Get the list of gif's under the preferred and opposing directory
        all_gifs = glob.glob("assets/animations/goal/all/*.gif")
        preferred_gifs = glob.glob("assets/animations/goal/preferred/*.gif")
        opposing_gifs = glob.glob("assets/animations/goal/opposing/*.gif")

        filename = "assets/animations/goal_light_animation.gif"
        
        # Use alternate animations if there is any in the respective folder
        if all_gifs:
            # Set opposing team goal animation here
            filename = random.choice(all_gifs)
            debug.info("General animation is: " + filename)

        if opposing_gifs:
            # Set opposing team goal animation here
            filename = random.choice(opposing_gifs)
            debug.info("Opposing animation is: " + filename)

        if id in self.data.pref_teams and preferred_gifs:
            # Set your preferred team goal animation here
            filename = random.choice(preferred_gifs)
            debug.info("Preferred animation is: " + filename)
        


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

            self.matrix.draw_image(("50%", 0), im, "center")
            self.matrix.render()

            frame_nub += 1
            sleep(0.1)

    def draw_end_period_indicator(self):
        """TODO: change the width depending how much time is left to the intermission"""
        color = self.matrix.graphics.Color(0, 255, 0)
        self.matrix.graphics.DrawLine(self.matrix.matrix, (self.matrix.width * .5) - 8, self.matrix.height - 2, (self.matrix.width * .5) + 8, self.matrix.height - 2, color)
        self.matrix.graphics.DrawLine(self.matrix.matrix, (self.matrix.width * .5) - 9, self.matrix.height - 1, (self.matrix.width * .5) + 9, self.matrix.height - 1, color)

    def draw_end_of_game_indicator(self):
        """TODO: change the width depending how much time is left to the intermission"""
        color = self.matrix.graphics.Color(255, 0, 0)
        self.matrix.graphics.DrawLine(self.matrix.matrix, (self.matrix.width * .5) - 8, self.matrix.height - 2, (self.matrix.width * .5) + 8, self.matrix.height - 2, color)
        self.matrix.graphics.DrawLine(self.matrix.matrix, (self.matrix.width * .5) - 9, self.matrix.height - 1, (self.matrix.width * .5) + 9, self.matrix.height - 1, color)

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

