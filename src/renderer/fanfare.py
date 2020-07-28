"""
    Some some variety of fanfare
"""
from PIL import Image, ImageDraw
from time import sleep
import debug
import serial

class Fanfare:
    def __init__(self, data, matrix):
        self.data = data
        self.matrix = matrix
        self.font = data.config.layout.font
        debug.info("987987*****************")
        debug.info(self.font)
        self.layout = data.config.config.layout.get_board_layout('fanfare')
        debug.info(self.layout)
        self.font_woo = self.layout.text.font
        self.ser = serial.Serial('/dev/ttyACM0', 19200, timeout=1)

    def listenForSerial(self):
        debug.info("Listening...")
        self.ser.flush()
        if self.ser.in_waiting > 0:
            line = self.ser.readline().decode('utf-8').rstrip()
            debug.log("received COMMUNICATION!")
            debug.log(line)
            if line == '1':
                self._draw_goal_light_display()
            elif line == '2':
                self._draw_goal_light_display()
            elif line == '3':
                self._draw_bailey_animation()
            elif line == '4':
                self._draw_pageau_animation()

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

    def _draw_bailey_animation(self):
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
